from __future__ import print_function
import networkx as nx
import mysql.connector
import re
import sys
import csv
from datetime import datetime
import glob
import os

results = {
      'activations': [],
      'distances': [],
      'nodesIn1' : [],
      'nodesIn2' : [],
      'nodesIn3' : [],
      'nodesIn4' : [],
      'nodesInRadii': [],
      'nodesInActivations': [],
      'resultInRadius': [],
      'resultInActivation': []
}

### Settings & Setup ##########################################################################################
vErr = True # verbose error logging
timeFilter = True # only include nodes from before question time
fullG = False # true if nodes have details, e.g. body
              # make this false if you're having unicode problems you don't want to debug 
login = {'user':'labuser', 'password':'selab527', 'host':'10.63.7.110', 'database':'network_t'}
if vErr: print("Connecting to db")
cnx = mysql.connector.connect(**login)
if vErr: print("Connected!")

### Begin by building dict of all users #######################################################################
if vErr: print("Building user database...")
query = "SELECT * FROM jira_user"

cursor = cnx.cursor()
cursor.execute(query)

usersByKey     = {}
usersByDisplay = {}
usersByID      = {}
for(id,org,jira_key,name,display,email_address,url,time_zone,locale) in cursor:
      usersByKey[jira_key]     = id
      usersByDisplay[display]  = id
      usersByID[id]            = [str(jira_key.encode('utf-8','replace')), str(display.encode('utf-8','replace'))]

cursor.close()

# Hardcode exceptions from answer set
usersByDisplay['Geoffrey De Smet'] = 171
usersByReference = {
      243 : {
            'Amos,'     : 178,
            'Ivo,'      : 1192,
            'Mike:'     : 1634,
            'Paul,'     : 45,
            'Tom,'      : 28,
            'Mark,'     : 133
      },
      67 : {
            'Edson,'    : 53,
            'Youcef'    : 4158,
            'Geoffrey,' : 171,
            'Davide,'   : 4149,
            'Chen,'     : 4146
      },
      145 : {
            'Chas:'     : 6286,
            'Mariano:'  : 6684,
            'Paul,'     : 6690,
            'Jim:'      : 113
      }
}

if vErr: print("User DB Complete!")

def add_edge_or_update_weight(G,a,b,w,attr):
      if(G.has_edge(a,b)):
            old_weight = G[a][b]['weight']
            new_weight = max(old_weight, w)
            attr.update({'weight':new_weight})
      else:
            attr.update({'weight':w})

      G.add_edge(a,b,**attr)

for f in glob.glob(os.getcwd()+'/answers/*.csv'):
      ### Settings & Setup ##########################################################################################
      projects = {"_432 RQ2 AIRFLOW.csv":432, "_433 RQ2 ANY23AnswerSet.csv":433, "54 RQ2 DASHBUILDER.csv":54, "67 Drools answer set.csv":67, "145 RQ2 IMMUNANT Answer set.csv":145, "243 JBTM answer set.csv":243}
      # weights = {'assignee':2, 'creator':2,'asked':4,'commented':3,'referenced in':2,'question':1,'comment':1}
      weights = {'assignee':2, 'creator':2,'asked':4,'commented':3,'referenced in':2,'question':1,'comment':1}
      answerCSV = "answers/"+os.path.basename(f)
      print(answerCSV)
      project = projects[os.path.basename(f)]
      

      G = nx.Graph()

      ### Get all of a project's issues #############################################################################
      # project = sys.argv[1]
      query = "SELECT * FROM jira_issue WHERE project = {}".format(project)

      cursor = cnx.cursor()
      cursor.execute(query)

      for(id,jira_id,jira_key,url,project,issue_type,priority,assignee,description,summary,creator,watches,votes,has_questions,timestamp,web_site,is_security,status) in cursor:
            issue = "Issue "+ str(id)
            if jira_key: jira_key = jira_key.encode('utf-8','replace')
            if summary: summary = summary.encode('utf-8','replace')
            if description: description = description.encode('utf-8','replace')

            if fullG: G.add_node(issue,type="issue",summary=str(summary),description=str(description),timestamp=str(timestamp),key=str(jira_key))
            else:     G.add_node(issue,type="issue",timestamp=str(timestamp))

            if (assignee != None):
                  assignee_label = "Person " + str(assignee)
                  if fullG: G.add_node(assignee_label, type="person", display=usersByID[assignee][1])
                  else:     G.add_node(assignee_label, type="person"    )
                  add_edge_or_update_weight(G,issue,assignee_label,weights['assignee'],{'assignee':1})

            if (creator  != None): 
                  creator_label = "Person " + str(creator)
                  if fullG: G.add_node(creator_label, type="person", display=usersByID[creator][1])
                  else:     G.add_node(creator_label, type="person")
                  add_edge_or_update_weight(G,issue,creator_label,weights['assignee'],{'creator':1})

      cursor.close()
      ### Get all of the issues' comments ###########################################################################      

      query = "SELECT * FROM jira_issue_comment WHERE issue IN ( SELECT id FROM jira_issue WHERE project = {})".format(project)
      cursor = cnx.cursor()
      cursor.execute(query)

      for(id,jira_id,author,url,body,issue,created,updated,parsetree,is_question,has_indicator,coref_need,evaluate_coref,answer_set) in cursor:
            issue = "Issue " + str(issue)

            # Add comment to graph, connect to issue
            if body: body = body.encode('utf-8','replace')
            if (is_question): 
                  comment = "Comment " + str(id)
                  if fullG: G.add_node(comment,type="question",body=str(body),timestamp=str(updated))
                  else:     G.add_node(comment,type="question",timestamp=str(updated))
                  add_edge_or_update_weight(G,comment,issue,weights['question'],{'question':1})
            else:
                  comment = "Comment " + str(id)
                  if fullG: G.add_node(comment,type="comment",body=str(body),timestamp=str(updated))
                  else:     G.add_node(comment,type="comment",timestamp=str(updated))
                  add_edge_or_update_weight(G,comment,issue,weights['comment'],{'comment':1})

            # Connect comment to author
            if (author != None):
                  author_label = "Person " + str(author)
                  if fullG: G.add_node(author_label,type="person", display=usersByID[author][1])
                  else:     G.add_node(author_label,type="person")

                  if (is_question):
                        add_edge_or_update_weight(G,comment,author_label,weights['asked'],{'asked':1})
                  else:
                        add_edge_or_update_weight(G,comment,author_label,weights['commented'],{'commented':1})

            # find all referenced users and add them to graph
            refs = re.findall('\[~(.+?)\]',str(body))
            for ref in refs:
                  if ref in usersByKey: # this isn't redundant: we add this in case query failed
                        userid = usersByKey[ref]
                        user   = "Person " + str(userid)
                        if fullG: G.add_node(user,type="person", display=usersByID[userid][1])
                        else:     G.add_node(user,type="person")
                        add_edge_or_update_weight(G,user,comment,weights['referenced in'],{'referenced in':1})
            refs = re.findall('[A-Z][a-z]+?,|[A-Z][a-z]+?:',str(body))
            for ref in refs:
                  if project in usersByReference:
                        if ref in usersByReference[project]:
                              userid = usersByReference[project][ref]
                              user   = "Person " + str(userid)
                              if fullG: G.add_node(user,type="person", display=usersByID[userid][1])
                              else:     G.add_node(user,type="person")
                              add_edge_or_update_weight(G,user,comment,weights['referenced in'],{'referenced in':1})

      cursor.close()

      ### Spreading Activation ######################################################################################
      def spreadActivation(g, src):
            g = g.copy();

            if src in g.node:
                  g.node[src]['activation'] = 1.0
                  g.node[src]['qa'] = 0

                  decay = 0.1

                  bfs = nx.bfs_edges(g,src)

                  for e in bfs:
                        cNode = e[1]
                        for pNode in g.neighbors(cNode):
                              if 'activation' in g.node[pNode]:
                                    weight = g[pNode][cNode]['weight']
                                    sActivation = g.node[pNode]['activation'] * (1 - (weight * decay))

                                    if 'activation' in g.node[cNode]:
                                          nActivation = g.node[cNode]['activation']
                                          newAct = max(nActivation, sActivation)
                                          oldAct = min(nActivation, sActivation)
                                          g.node[cNode]['activation'] = newAct + ((1-newAct)*oldAct*0.01)
                                          # g.node[cNode]['activation'] = newAct
                                    else:
                                         g.node[cNode]['activation'] = sActivation
                  return g
            else:
                  return -1

      ### Compare Questions to Answers ################################################################################
      # for each row of the CSV, this function will be called
      def rowAnalysis(row):
            body = row[0]
            asker = row[1].strip()
            answered = row[2]
            answerer = row[3].strip()

            if answered:
                  #TODO: replace with body[0:40]
                  questionSnippet  = body[0:20].replace(" ", "%") # some spaces might be new lines so we replace them with wildcards
                  questionPerson   = asker
                  if questionPerson in usersByDisplay:
                        questionPersonID = usersByDisplay[questionPerson]

                        query = 'SELECT * FROM (SELECT * FROM jira_issue_comment WHERE author={}) AS q1 WHERE q1.body LIKE "{}%";'.format(questionPersonID,questionSnippet)
                        cursor = cnx.cursor()

                        try: 
                              cursor.execute(query)
                        except mysql.connector.errors.ProgrammingError:
                              if vErr: print("Failed Query: " + query)

                        question = None
                        for(id,jira_id,author,url,body,issue,created,updated,parsetree,is_question,has_indicator,coref_need,evaluate_coref,answer_set) in cursor:
                              question = "Comment " + str(id)
                        if question: 
                              # remove nodes that came after question
                              if question in G.node:
                                    timeformat = '%Y-%m-%d %H:%M:%S'
                                    tQuestion = datetime.strptime(G.node[question]['timestamp'], timeformat)

                                    g = G.copy()
                                    if timeFilter:
                                          sgFilter = []
                                          tAnalysis = True
                                          for n in g.nodes(data='timestamp'):
                                                if n[1] != None:
                                                      try :
                                                            tNode = datetime.strptime(n[1], timeformat)
                                                            if tNode <= tQuestion:
                                                                  sgFilter.append(n[0])
                                                      except ValueError as err:
                                                            # if vErr: print("Value Error when transcribing timestamp. You may have to disable timestamp analysis.")
                                                            tAnalysis = False
                                                else:
                                                      sgFilter.append(n[0])

                                          if tAnalysis: g = g.copy().subgraph(sgFilter)

                                    # and spread activation
                                    q = spreadActivation(g, question)
                                    answerPerson = answerer
                                    if answerPerson in usersByDisplay:
                                          answer   = 'Person ' + str(usersByDisplay[answerPerson])
                                          if answer in q.node:
                                                path = []
                                                try: 
                                                      # network analysis!
                                                      radCut = 5
                                                      actCut = 0.65

                                                      path = nx.shortest_path(q,question,answer)
                                                      activation = q.node[answer]['activation']
                                                      print("Activation: {0:.2f}, Distance: {1}, Path: {2} ".format(activation, len(path), path))
                                                      nodesInActivation = 0
                                                      for n in q.nodes(data='activation'): 
                                                            if n[1] != None: 
                                                                  if n[1] >= actCut:
                                                                        nodesInActivation += 1

                                                      
                                                      nodesIn1 = nx.number_of_nodes(nx.ego_graph(q,question,radius=2))
                                                      nodesIn2 = nx.number_of_nodes(nx.ego_graph(q,question,radius=3))
                                                      nodesIn3 = nx.number_of_nodes(nx.ego_graph(q,question,radius=4))
                                                      nodesIn4 = nx.number_of_nodes(nx.ego_graph(q,question,radius=5))
                                                      nodesInRadius = nx.number_of_nodes(nx.ego_graph(q,question,radius=radCut))
                                                      # print("{0:4} {1:4}".format(nodesInRadius, nodesInActivation))
                                                      
                                                      results['activations'].append(activation)
                                                      results['distances'].append(len(path))
                                                      results['nodesIn1'].append(nodesIn1)
                                                      results['nodesIn2'].append(nodesIn2)
                                                      results['nodesIn3'].append(nodesIn3)
                                                      results['nodesIn4'].append(nodesIn4)
                                                      results['nodesInRadii'].append(nodesInRadius)
                                                      results['nodesInActivations'].append(nodesInActivation)
                                                      if len(path) <= radCut:  results['resultInRadius'].append(1)
                                                      else:                    results['resultInRadius'].append(0)
                                                      if activation >= actCut: results['resultInActivation'].append(1)
                                                      else:                    results['resultInActivation'].append(0)

                                                except nx.exception.NetworkXNoPath:
                                                      print("Path Not Found for " + question + " -> " + answer)
                                                      results['activations'].append(-1)
                                                      results['distances'].append(-1)
                                                      results['nodesInRadii'].append(-1)
                                                      results['nodesInActivations'].append(-1)

                                                q.node[answer]['qa'] = 1
                                                if timeFilter: nx.write_graphml(q,"./{}.graphml".format(question))
                                                else: nx.write_graphml(q,"./{}_noFilter.graphml".format(question))
                                                
                                                

                                          else:
                                                if vErr: print(answerPerson + " not found in Graph")
                                          # a = spreadActivation(G, answer)
                                          # nx.write_graphml(a,"./project_{}_answer.graphml".format(project))
                                    else:
                                          if vErr: print(answerPerson + ' not found in DB!')
                              else:
                                    if vErr: print(question + ' not found in graph!')
                        else: 
                              if vErr: print('Question not found in DB! Author: {}, Question: {}'.format(questionPersonID,questionSnippet))
                  else:
                        if vErr: print(questionPerson + ' not found in DB!')

      with open(answerCSV,'rb') as f:
            reader=csv.reader(f)

            for row in reader:
                  rowAnalysis(row) # this is a function so that each iteration has its own workspace


      f.close()
### Close up shop #############################################################################################
cnx.close()

print(results['activations'])
print(results['distances'])
print(results['nodesIn1'])
print(results['nodesIn2'])
print(results['nodesIn3'])
print(results['nodesIn4'])
print(results['nodesInRadii'])
print(results['nodesInActivations'])
print(results['resultInRadius'])
print(results['resultInActivation'])


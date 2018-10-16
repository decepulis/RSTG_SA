# Darius Cepulis
# cepulide@mail.uc.edu
# de.cepuils@gmail.com
#
# RSTG-SA.py
#
# Built and Tested with Anaconda for Python 3.6
# https://www.anaconda.com/download/
#
# Might still work with Python 2.7
# from __future__ import print_function
# 
# I.   Utility IO Functions
#      functions for reading and writing pickles
#
# II.  MySQL Database Functions
#      class with functions for connecting to and reading MySQL
#
# III. Graph Manipulation Functions
#      class with functions for creating, reading, and writing networkx graphs
#
# IV.  Main
#      procedure for reading CSVs with questions and answers
#      producting graphs, and analyzing the distance between questions and answers
#
#
#
# Significant caching is utilized in this script
# Delete cache to rebuild stuff
# View cache in ./cache 
# Operations that require querying the MySQL database are the slowest


import mysql.connector # https://dev.mysql.com/downloads/connector/python/
                       # conda install -c anaconda mysql-connector-python
import pickle
import os, os.path
import errno
import networkx as nx
import re
import glob
import csv
from datetime import datetime
import RAKE # pip install python-rake

#########################################################################################################
### Utility IO Functions ################################################################################
#########################################################################################################

# input:  obj   - python object, e.g., a dictionary
#         fname - filename, without folder or extension
def saveObject(obj, fname):
    with safeOpenWrite('cache/'+ fname + '.pkl') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

# input:  fname - filename, without folder or extension
# output: python object, e.g., a dictionary
def loadObject(fname):
    try:
        with open('cache/' + fname + '.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        raise

# input: path - make directories along this path
def mkdirPath(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

# input:  path - open this file for writing, creating folders if necessary
# output: open file
def safeOpenWrite(path):
    mkdirPath(os.path.dirname(path))
    return open(path, 'wb')

# input:  i - character to check
# output: boolean representing whether is valid
def isValidXMLChar(i):
    # XML standard defines a valid char as::
    # Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    return (
        0x20 <= i <= 0xD7FF
        or i in (0x9, 0xA, 0xD)
        or 0xE000 <= i <= 0xFFFD
        or 0x10000 <= i <= 0x10FFFF
        )

# input:  s - string
# output  string clean of xml characters
def cleanXMLString(s):
    return ''.join(c for c in s if isValidXMLChar(ord(c)))




#########################################################################################################
### MySQL Database Functions ############################################################################
#########################################################################################################
class dbManager():
    # input:  login = {'user':username, 'password':password, 'host':host, ['database': database, ...]}
    def __init__(self, login):
        self.rake = RAKE.Rake(RAKE.SmartStopList()) # used later for keyword extraction

        print('Connecting to database...')
        login['connection_timeout'] = 5

        try:
            self.cnx = mysql.connector.connect(**login)
        except mysql.connector.errors.InterfaceError as exc:
            if exc.errno == 2003:
                print('Connection with database timed out. Attempting to run with cached data.')
            else:
                print('Connection with database failed. Attempting to run with cached data.')
                print(exc)
            self.cnx = None

        self.loadUsersFromCache()

    # input:  connection from dbConnection()
    # output: usersByKey       - {username:  id}
    #         usersByDisplay   - {full name: id}
    #         usersByID        - {id : {'key':key, 'display':display}}
    #         usersByReference - { project #: {'Name, ': id, 'Name: ', id} }
    def loadUsersFromCache(self):
        print('Loading users from cache...')
        try:
            usersByKey       = loadObject('usersByKey')
            usersByDisplay   = loadObject('usersByDisplay')
            usersByID        = loadObject('usersByID')
            usersByReference = loadObject('usersByReference')

            self.usersByKey       = usersByKey
            self.usersByDisplay   = usersByDisplay
            self.usersByID        = usersByID
            self.usersByReference = usersByReference

        except FileNotFoundError:
            print('Loading from cache failed. Attempting to rebuild from database...')
            self.loadUsersFromDB()

    # input:  connection from dbConnection()

    # output: usersByKey       - {username:  id}
    #         usersByDisplay   - {full name: id}
    #         usersByID        - {id : {key, display}}
    #         usersByReference - { project #: {'Name, ': id, 'Name: ', id} }
    def loadUsersFromDB(self):
        print('Loading users from database...')

        query = "SELECT * FROM jira_user"
        cursor = self.cnx.cursor()
        cursor.execute(query)

        usersByKey     = {}
        usersByDisplay = {}
        usersByID      = {}
        for(id,org,jira_key,name,display,email_address,url,time_zone,locale) in cursor:
              usersByKey[jira_key]     = id
              usersByDisplay[display]  = id
              usersByID[id]            = {'key':jira_key, 'display':display} # refactor as namedtuple?

        cursor.close()

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

        saveObject(usersByKey,       'usersByKey')
        saveObject(usersByDisplay,   'usersByDisplay')
        saveObject(usersByID,        'usersByID')
        saveObject(usersByReference, 'usersByReference')

        self.usersByKey       = usersByKey
        self.usersByDisplay   = usersByDisplay
        self.usersByID        = usersByID
        self.usersByReference = usersByReference

    # input and output:
    #   * getUser(key     = <user key>)
    #     returns <user ID> as int
    #   * getUser(display = <user name>)
    #     returns <user ID> as int
    #   * getUser(id = <user id>, ret = <key or display>)
    #     returns <user key> or <user display> as string
    #   * getUser(reference = <user reference, e.g. 'Paul, '>, project = <project number>)
    #     returns <user ID> as int
    def getUser(self, **kwargs):
        try:
            if 'key' in kwargs:
                return self.usersByKey[kwargs['key']]
            elif 'display' in kwargs:
                return self.usersByDisplay[kwargs['display']]
            elif 'id' in kwargs:
                try:
                    return self.usersByID[kwargs['id']][kwargs['ret']]
                except KeyError:
                    raise
            elif 'reference' in kwargs:
                try:
                    return self.usersByReference[kwargs['project']][kwargs['reference']]
                except KeyError:
                    raise
        except KeyError:
            raise

    # input: project - int representing project number in database
    #        graph   - graph to populate with project issues and their related people
    def addProjectIssuesToGraph(self,project,graph):
        print('Populating graph with issues from project {}...'.format(project))

        query = "SELECT * FROM jira_issue WHERE project = {}".format(project)
        cursor = self.cnx.cursor()
        cursor.execute(query)

        for(id,jira_id,jira_key,url,project,issue_type,priority,assignee,description,summary,creator,watches,votes,has_questions,timestamp,web_site,is_security,status) in cursor:
            issue = "Issue "+ str(id)

            graph.addNode(issue,type="issue",summary=summary,description=description,timestamp=str(timestamp),key=jira_key)

            # Connect issue to keywords
            '''
            keywords = (word[0] for word in self.rake.run('{} {}'.format(summary,description)) if word[1]>=1.0)
            for word in keywords:
                graph.addNode(word,type="keyword")
                graph.addEdgeOrUpdateWeight(issue,word,'keyword')
            '''

            # Connect issue to people
            if (assignee != None):
                  assignee_label = "Person " + str(assignee)
                  try:
                      graph.addNode(assignee_label, type="person", display=self.getUser(id=assignee,ret='display'))
                      graph.addEdgeOrUpdateWeight(issue,assignee_label,'assignee')
                  except KeyError:
                    if vErr: print("User {} not found".format(assignee))

            if (creator  != None): 
                  creator_label = "Person " + str(creator)
                  try:
                      graph.addNode(creator_label, type="person", display=self.getUser(id=creator,ret='display'))
                      graph.addEdgeOrUpdateWeight(issue,creator_label,'creator')
                  except KeyError:
                    if vErr: print("User {} not found".format(creator))

        cursor.close()

    # input: project - int representing project number in database
    #        graph   - graph to populate with project issues and their related peopl
    def addProjectCommentsToGraph(self,project,graph):
        print('Populating graph with comments and questions from project {}...'.format(project))

        query = "SELECT * FROM jira_issue_comment WHERE issue IN ( SELECT id FROM jira_issue WHERE project = {})".format(project)
        cursor = self.cnx.cursor()
        cursor.execute(query)

        for(id,jira_id,author,url,body,issue,created,updated,parsetree,is_question,has_indicator,coref_need,evaluate_coref,answer_set) in cursor:
            issue = "Issue " + str(issue)

            # Add comment to graph, connect to issue
            comment = "Comment " + str(id)
            if is_question: 
                  graph.addNode(comment,type="question",body=body,timestamp=str(updated))
                  graph.addEdgeOrUpdateWeight(comment,issue,'question')
            else:
                  graph.addNode(comment,type="comment",body=body,timestamp=str(updated))
                  graph.addEdgeOrUpdateWeight(comment,issue,'comment')

            # Connect comment to keywords
            '''
            if body:
                keywords = (word[0] for word in self.rake.run(body) if word[1]>=1.0)
                for word in keywords:
                    graph.addNode(word,type="keyword")
                    graph.addEdgeOrUpdateWeight(comment,word,'keyword')
            '''

            # Connect comment to author
            if author:
                  author_label = "Person " + str(author)
                  graph.addNode(author_label,type="person", display=self.getUser(id=author, ret='display'))

                  if (is_question):
                        graph.addEdgeOrUpdateWeight(comment,author_label,'asked')
                  else:
                        graph.addEdgeOrUpdateWeight(comment,author_label,'posted')

            # find all referenced users and add them to graph
            # 1) Referenced by username
            refs = re.findall('\[~(.+?)\]',str(body))
            for ref in refs:
                try:
                    userid = self.getUser(key=ref)
                    user   = "Person " + str(userid)
                    graph.addNode(user,type="person", display=self.getUser(id=userid, ret='display'))
                    graph.addEdgeOrUpdateWeight(user,comment,'referenced in')
                except KeyError:
                    if vErr: print("{} not found".format(ref))
                    pass

            # 2) Referenced by first name
            refs = re.findall('[A-Z][a-z]+?,|[A-Z][a-z]+?:',str(body))
            for ref in refs:
                try:
                    userid = self.getUser(reference=ref, project=project)
                    user   = "Person " + str(userid)
                    graph.addNode(user,type="person", display=self.getUser(id=userid, ret='display'))
                    graph.addEdgeOrUpdateWeight(user,comment,'referenced in')
                except KeyError:
                    if vErr: print('Reference "{}" not found in project {}'.format(ref,project))
                    pass

        cursor.close()


    # input: project - int representing project number in database
    #        graph   - graph to populate with project issues and their related peopl
    def addProjectToGraph(self,project,graph):
        self.addProjectIssuesToGraph(project,graph)
        self.addProjectCommentsToGraph(project,graph)

    # input:  userDisplay - The full name of the commenting user, as a string
    #         comment     - The body of the comment or question
    # output: questions   - returns array of node names that match input
    #                       e.g. ["Comment 123", "Comment 456"] or e.g. []
    def findUserComment(self,userDisplay,comment):
        # we begin by replacing spaces with wildcards because
        # some spaces from sample data are actually new lines in the db
        comment = comment[0:40].replace(" ", "%").replace('"','\\"')
        try:
            userid   = self.getUser(display=userDisplay)
        except KeyError:
            if vErr: print("User " + userDisplay + " not found.")
            return []

        query = 'SELECT * FROM (SELECT * FROM jira_issue_comment WHERE author={}) AS q1 WHERE q1.body LIKE "{}%";'.format(userid,comment)
        cursor = self.cnx.cursor()
        cursor.execute(query)

        # now we find all 
        comments = []
        for(id,jira_id,author,url,body,issue,created,updated,parsetree,is_question,has_indicator,coref_need,evaluate_coref,answer_set) in cursor:
            comments.append("Comment " + str(id))
        cursor.close()

        return comments



#########################################################################################################
### Graph Manipulation Functions ########################################################################
#########################################################################################################

class graph():
    # Initialize graph() with a project and database to attempt to load from cache
    # input: project - [optional] project number to load
    #        db -      [optional] database to load from if project not in cache
    def __init__(self, **kwargs):
        self.weights = {'assignee':2, 'creator':2,'asked':4,'posted':3,'referenced in':2,'question':1,'comment':1, 'keyword':4}
        self.timeformat = '%Y-%m-%d %H:%M:%S'

        if 'project' in kwargs and 'db' in kwargs:
            self.loadProject(kwargs['project'], kwargs['db'])
        elif 'graph' in kwargs:
            self.G = kwargs['graph'].copy()
        else:
            self.G = nx.Graph()

    # input: project - project number to load from cache or db
    #        db      - db from which to load project if cache fails
    def loadProject(self, project, db):
        try:
            print('Loading project {} graph from cache...'.format(project))
            self.G = loadObject('{}_graph'.format(project))
            print('Loading Complete!')
        except IOError:
            print('Project {} not in cache. Attempting to reload...'.format(project))
            self.G = nx.Graph()
            db.addProjectToGraph(project,self)
            saveObject(self.G,'{}_graph'.format(project))

    # input:  typ - type of edge
    # output: weight of edge
    def getWeight(self,typ):
        try: 
            return self.weights[typ]
        except KeyError:
            raise

    # input: G    - graph to search
    #        a    - node 1
    #        b    - node 2
    #        type - type of edge to add
    def addEdgeOrUpdateWeight(self,a,b,typ):
            w = self.getWeight(typ)
            attr = {'type' : typ}

            if(self.G.has_edge(a,b)):
                old_weight = self.G[a][b]['weight']
                new_weight = max(old_weight, w)
                attr.update({'weight':new_weight})
            else:
                attr.update({'weight':w})

            self.G.add_edge(a,b,**attr)

    # input:  node - unique node name in graph
    #         attr_dict - dictionary of attributes to give to the node
    def addNode(self,node,**attr):
        self.G.add_node(node,**attr)

    # input:  timestamp  - datetime object
    #                      e.g. datetime.strptime(G.node[question]['timestamp'],self.timeformat)
    # output: subgraph before timestamp
    def newSubgraphBeforeTimestamp(self,timestamp):
        g = self.G.copy()
        sgFilter = []
        for n in g.nodes(data='timestamp'):
            if n[1] == None: # if there is no timestamp in the node it's a person. Add.
                sgFilter.append(n[0])
            else:
                tNode = datetime.strptime(n[1], self.timeformat)
                if tNode <= timestamp:
                    sgFilter.append(n[0])

        return g.subgraph(sgFilter)

    # output: copy of current graph
    def newGraphCopy(self):
        return self.G.copy()

    # Traverses nodes, spreads activation from predecessors
    # input: questionNode - name of node from which to spread (e.g. 'Comment 123')
    #        issueNode    - name of issue node for quesiton node; also activated to 1
    #        spaceDecay - rate, from 0-1, at which activation decays relative to space
    #                     0.1 recommended
    def spreadActivationSimple(self,questionNode,issueNode,spaceDecay):
        try:
            self.G.node[questionNode]['activation'] = 1.0
            self.G.node[questionNode]['qa'] = 'question'

            self.G.node[issueNode]['activation'] = 1.0
            self.G.node[issueNode]['qa'] = 'issue'

            bft = nx.bfs_edges(self.G,questionNode)
            for edge in bft:
                postNode = edge[1]
                for preNode in self.G.neighbors(postNode):
                    if 'activation' in self.G.node[preNode]:
                        weight = self.G[preNode][postNode]['weight']
                        calcActivation = self.G.node[preNode]['activation'] * (1 - (weight * spaceDecay))

                        if 'activation' in self.G.node[postNode]:
                            currentActivation = self.G.node[postNode]['activation']
                            newActivation = max(calcActivation,currentActivation)
                            self.G.node[postNode]['activation'] = newActivation
                        else:
                            self.G.node[postNode]['activation'] = calcActivation
        except KeyError:
            raise

    # Traverses nodes, spreads activation from predecessors
    # input: questionNode - name of node from which to spread (e.g. 'Comment 123')
    #        issueNode    - name of issue node for quesiton node; also activated to 1
    #        spaceDecay - rate, from 0-1, at which activation decays relative to space
    #                     0.1 recommended
    def spreadActivationComplete(self,questionNode,issueNode,spaceDecay):
        try:
            self.G.node[questionNode]['activation'] = 1.0
            self.G.node[questionNode]['qa'] = 'question'

            self.G.node[issueNode]['activation'] = 1.0
            self.G.node[issueNode]['qa'] = 'issue'

            bft = nx.bfs_edges(self.G,questionNode)
            i = 0
            for edge in bft:
                preNode = edge[0]
                for postNode in self.G.neighbors(preNode):
                    if 'activation' in self.G.node[preNode]: # which it really should always be
                        weight = self.G[preNode][postNode]['weight']
                        calcActivation = self.G.node[preNode]['activation'] * (1 - (weight * spaceDecay))

                        if 'activation' in self.G.node[postNode]:
                            currentActivation = self.G.node[postNode]['activation']
                            newActivation = max(calcActivation,currentActivation)
                            self.G.node[postNode]['activation'] = newActivation
                        else:
                            self.G.node[postNode]['activation'] = calcActivation
                    else:
                        print('hello!')
        except KeyError:
            raise

    # Finds shortest path between two nodes
    # with option to analyze by weight
    # input: sourceNode      - source node
    #        destinationNode - destination node (duh)
    #        weight          - shortest path, including weight? True/False
    def findPath(self,sourceNode,destinationNode, weight=False):
        try:
            if weight:
                return nx.shortest_path(self.G,sourceNode,destinationNode, weight='weight')
            else:
                return nx.shortest_path(self.G,sourceNode,destinationNode)
        except nx.exception.NetworkXNoPath:
            raise

    # Finds shortest path between two nodes
    # with option to analyze by weight
    # input: sourceNode      - source node
    #        destinationNode - destination node (duh)
    #        weight          - shortest path, including weight? True/False
    def findPaths(self,sourceNode,destinationNode, weight=False):
        try:
            if weight:
                return nx.all_shortest_paths(self.G,sourceNode,destinationNode, weight='weight')
            else:
                return nx.all_shortest_paths(self.G,sourceNode,destinationNode)
        except nx.exception.NetworkXNoPath:
            raise

    # input:  node - node whose activation to inspect
    # output: activation of node
    def getNodeActivation(self,node):
        return self.G.node[node]['activation']

    # output: the number of nodes over input activationCutoff
    def numNodesInActivation(self,activationCutoff):
        return sum(1 for n in self.G.nodes(data='activation') if (n[1] != None and n[1] >= activationCutoff))

    # output: the number of nodes within radius of sourceNode
    # input:  radius -     number of hops from sourceNode within which to count
    #         sourceNode - node from which to count
    def numNodesInRadius(self,radius,sourceNode):
        return nx.number_of_nodes(nx.ego_graph(self.G,sourceNode,radius=radius))

    # input:  node to search for
    # output: bool
    def nodeInGraph(self,node):
        return node in self.G.node

    # input: node - node whose attribute to set
    #        attribute - attribute to set
    #        value - value to set attribute to
    def setAttribute(self,node,attribute,value):
        self.G.node[node][attribute] = value

    # input:  node before which to create graph
    # output: subgraph before node
    def newSubgraphBeforeNode(self,node):
        tQuestion = datetime.strptime(self.G.node[node]['timestamp'],self.timeformat)
        return self.newSubgraphBeforeTimestamp(tQuestion)

    # input: filename - filename of saved graph
    def saveAsGraphML(self,filename):
        # clean strucutre
        for node in self.G.node:
            for attrib in self.G.node[node]:
                if type(self.G.node[node][attrib]) == str:
                    text = self.G.node[node][attrib]
                    clean = re.sub(u'[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\U00010000-\U0010FFFF]+', '', text)
                    self.G.node[node][attrib] = clean

                elif self.G.node[node][attrib] == None:
                    self.G.node[node][attrib] = 'None'
        # write file
        mkdirPath('./graphs/')
        nx.write_graphml(self.G, './graphs/'+filename+'.graphml')

    # input: filename - filename of saved graph
    def saveAsGML(self,filename):
        # clean strucutre
        for node in self.G.node:
            for attrib in self.G.node[node]:
                if type(self.G.node[node][attrib]) == str:
                    text = self.G.node[node][attrib]
                    clean = re.sub(u'[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\U00010000-\U0010FFFF]+', '', text)
                    self.G.node[node][attrib] = clean

                elif self.G.node[node][attrib] == None:
                    self.G.node[node][attrib] = 'None'
        # write file
        mkdirPath('./graphs/')
        nx.write_gml(self.G, './graphs/'+filename+'.gml')


#########################################################################################################
### Main ################################################################################################
#########################################################################################################
if __name__ == '__main__':
    # == SETUP ==========================================================================================
    vErr = True # Verbose Error Output
    
    login = {'user':'labuser', 'password':'selab527', 'host':'10.63.7.110', 'database':'network_t'}
    # login = {'user':'root', 'password':'foraging', 'host':'127.0.0.1', 'database':'network_t'}
    db = dbManager(login)

    try:
        questionDB = loadObject('questionDB')
    except FileNotFoundError:
        print('QuestionDB not cached. Rebuilding...')
        questionDB = {}

    # == For Each Project ===============================================================================
    projects = {"_432 RQ2 AIRFLOW.csv":432, "_433 RQ2 ANY23AnswerSet.csv":433, "54 RQ2 DASHBUILDER.csv":54, "67 Drools answer set.csv":67, "145 RQ2 IMMUNANT Answer set.csv":145, "243 JBTM answer set.csv":243}
    # projects = {"54 RQ2 DASHBUILDER.csv":1, "67 Drools answer set.csv":2, "145 RQ2 IMMUNANT Answer set.csv":4, "243 JBTM answer set.csv":3}
    for f in glob.glob(os.getcwd()+'/answers/*.csv'):
        answerCSV = 'answers/'+os.path.basename(f)
        print(answerCSV)

        # = = load project from db and into a graph  = = = = = = = = = = = = = = = = = = = = = = = = = = 
        project = projects[os.path.basename(f)]
        try: 
            g = graph(project=project,db=db)
        except AttributeError:
            exit('Can not proceed without server connection.')

        g.saveAsGML(str(project))

        # = = go through each answer and analyze = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
        with open(answerCSV,encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                # -- Parse Row -------------------------------------------------------------------------
                body     = row[0].strip()
                asker    = row[1].strip()
                answered = row[2].strip()
                answerer = row[3].strip()
                if not answered:
                    # if vErr: print('Question not answered.')
                    continue # onto the  next row in the reader

                try:
                    answer = 'Person ' + str(db.getUser(display=answerer))
                except KeyError:
                    if vErr: print('Answerer {} is not in database.'.format(answerer))
                    continue # onto the next row in the reader

                # -- Filter by Question ----------------------------------------------------------------
                try:
                    question = questionDB[body]
                except KeyError:
                    questions = db.findUserComment(asker,body)
                    question = None
                    for qu in questions:      # for all the user's comments that have the same body...
                        if g.nodeInGraph(qu): # we pick the first one in our graph
                            question = qu
                    if not question: # and if we didn't find a question...
                        if vErr: print('Question not found in graph.')
                        continue # onto the next row in the reader
                    questionDB[body] = question

                try:
                    q = loadObject(question)
                except FileNotFoundError:
                    q = graph(graph = g.newSubgraphBeforeNode(question)) # we filter our graph by time
                    
                    # -- Find Answer ------------------------------------------------------------------------
                    if not q.nodeInGraph(answer):
                        if vErr: print('Answerer {} is not in network.'.format(answerer))
                        continue

                    q.setAttribute(answer,'qa','answer')
                    saveObject(q,question)

                # -- Spread and Analyze-------------------------------------------------------------------
                q.spreadActivationSimple(question,issue,0.1)
                try: 
                    paths = list(q.findPaths(question, answer))
                    answerActivation = q.getNodeActivation(answer)
                    print("Activation: {0:.2f}, Paths: {1:2d}, Distance: {2}, Sample: {3} ".format(answerActivation, len(paths), len(paths[0]), paths[0]))


                except nx.exception.NetworkXNoPath:
                    print("Path Not Found for " + question + " -> " + answer)

                # q.saveAsGraphML(question)

    saveObject(questionDB,'questionDB')
                    




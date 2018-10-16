clear all
close all
clc

d1 = [2, 4, 4, 2, 4, 3, 2, 4, 2, 4, 2, 6, 4, 4, 4, 4, 3, 4, 2, 4, 2, 2, 4, 4, 4, 2, 4, 4, 4, 4, 4, 2, 3, 3, 3, 2, 4, 3, 3, 2, 2, 2, 2, 5, 2, 4, 4, 3, 3, 3, 3, 4, 4, 3, 3, 2, 4, 4, 4, 4, 2, 4, 4, 3, 2, 4, 2, 4, 3, 3, 3, 3, 3, 3, 3, 4, 4, 3, 4, 100, 4, 3, 5, 2, 4, 5, 3, 4, 2, 4, 4, 4, 2, 2, 2, 2, 2, 2, 4, 2, 4, 3, 4, 4, 2, 4, 2, 3, 2, 2, 2];
d2 = [2, 3, 4, 2, 3, 3, 2, 3, 2, 3, 2, 5, 3, 4, 4, 4, 3, 3, 2, 3, 2, 2, 3, 3, 4, 2, 3, 3, 3, 3, 5, 2, 3, 3, 3, 2, 3, 3, 3, 2, 2, 2, 2, 5, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 3, 3, 3, 4, 2, 3, 3, 3, 2, 3, 2, 4, 3, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 100, 3, 3, 4, 2, 3, 4, 3, 4, 2, 4, 3, 3, 2, 2, 2, 2, 2, 2, 3, 2, 3, 3, 3, 3, 2, 3, 2, 3, 2, 2, 2]

n1 = hist(d1, unique(d1));
n1 = [n1(1:4) n1(5)+n1(6)];
n2 = hist(d2, unique(d2));

h = pie(n2);

hText = findobj(h,'Type','text');                        % text object handles
percentValues = get(hText,'String')';                    % percent values
txt = {'One: ', 'Two: ', 'Three: ', 'Four: ', 'Other: '}; % strings
combinedtxt = strcat(txt,percentValues);                 % strings and percent values
oldExtents_cell = get(hText,'Extent');                   % cell array
oldExtents = cell2mat(oldExtents_cell);                  % numeric array

hText(1).String = combinedtxt(1);
hText(2).String = combinedtxt(2);
hText(3).String = combinedtxt(3);
hText(4).String = combinedtxt(4);
hText(5).String = combinedtxt(5);

newExtents_cell = get(hText,'Extent');  % cell array
newExtents = cell2mat(newExtents_cell); % numeric array 
width_change = newExtents(:,3)-oldExtents(:,3);
signValues = sign(oldExtents(:,1));
offset = signValues.*(width_change/2);
textPositions_cell = get(hText,{'Position'}); % cell array
textPositions = cell2mat(textPositions_cell); % numeric array
textPositions(:,1) = textPositions(:,1) + offset; % add offset 
%textPositions = textPositions .* 0.0005;

hText(1).Position = textPositions(1,:);
hText(2).Position = textPositions(2,:);
hText(3).Position = textPositions(3,:);
hText(4).Position = textPositions(4,:)+[0.02 0 0];
hText(5).Position = textPositions(5,:)-[0.02 0 0];

fSize = 18;
hText(1).FontSize = fSize;
hText(2).FontSize = fSize;
hText(3).FontSize = fSize;
hText(4).FontSize = fSize;
hText(5).FontSize = fSize;

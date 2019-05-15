import requests
import csv
import time
import os.path
from collections import Counter
from datetime import datetime
import urllib3
import dsFunc

baseURL, email, password, filePath, verify, skipColl, sec = dsFunc.instSelect()

date = datetime.now().strftime('%Y-%m-%d %H.%M.%S') + '/'
filePathComplete = filePath + 'completeValueLists' + date
filePathUnique = filePath + 'uniqueValueLists' + date

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

startTime = time.time()
data = {'email': email, 'password': password}
header = {'content-type': 'application/json', 'accept': 'application/json'}
session = requests.post(baseURL + '/rest/login', headers=header,
                        verify=verify, params=data).cookies['JSESSIONID']
cookies = {'JSESSIONID': session}
headerFileUpload = {'accept': 'application/json'}

status = requests.get(baseURL + '/rest/status', headers=header,
                      cookies=cookies, verify=verify).json()
userFullName = status['fullname']
print('authenticated', userFullName)

collectionIds = []
endpoint = baseURL + '/rest/communities'
communities = requests.get(endpoint, headers=header, cookies=cookies,
                           verify=verify).json()
for i in range(0, len(communities)):
    communityID = communities[i]['uuid']
    collections = requests.get(baseURL + '/rest/communities/'
                               + str(communityID) + '/collections',
                               headers=header, cookies=cookies,
                               verify=verify).json()
    for j in range(0, len(collections)):
        collectionID = collections[j]['uuid']
        if collectionID not in skipColl:
            collectionIds.append(collectionID)

os.mkdir(filePathComplete)
os.mkdir(filePathUnique)

for number, collectionID in enumerate(collectionIds):
    collectionsRemaining = len(collectionIds) - number
    print(collectionID, 'Collections remaining: ', collectionsRemaining)
    collSels = '&collSel[]=' + collectionID
    offset = 0
    recordsEdited = 0
    items = ''
    while items != []:
        setTime = time.time()
        endpoint = baseURL
        + '/rest/filtered-items?query_field[]=*&query_op[]=exists&query_val[]='
        + collSels + '&expand=metadata&limit=20&offset=' + str(offset)
        response = requests.get(endpoint, headers=header, cookies=cookies,
                                verify=verify).json()
        items = response['items']
        for item in items:
            metadata = item['metadata']
            for i in range(0, len(metadata)):
                if metadata[i]['key'] != 'dc.description.provenance':
                    key = metadata[i]['key']
                    try:
                        value = metadata[i]['value']
                    except ValueError:
                        value = ''
                    for i in range(0, len(metadata)):
                        if metadata[i]['key'] == 'dc.identifier.uri':
                            uri = metadata[i]['value']
                    if os.path.isfile(filePathComplete + key
                                      + 'ValuesComplete.csv') is False:
                        f = csv.writer(open(filePathComplete + key
                                            + 'ValuesComplete.csv', 'w'))
                        f.writerow(['handle'] + ['value'])
                        f.writerow([uri] + [value])
                    else:
                        f = csv.writer(open(filePathComplete + key
                                            + 'ValuesComplete.csv', 'a'))
                        f.writerow([uri] + [value])
        offset = offset + 20
        print(offset)

        dsFunc.elapsedTime(setTime, 'Set run time')

    dsFunc.elapsedTime(startTime, 'Collection run time')

dsFunc.elapsedTime(startTime, 'Complete value list creation time')
#
for fileName in os.listdir(filePathComplete):
    reader = csv.DictReader(open(filePathComplete + fileName))
    fileName = fileName.replace('Complete', 'Unique')
    valueList = []
    for row in reader:
        valueList.append(row['value'])
    valueListCount = Counter(valueList)
    f = csv.writer(open(filePathUnique + fileName, 'w'))
    f.writerow(['value'] + ['count'])
    for key, value in valueListCount.items():
        f.writerow([key] + [str(value).zfill(6)])

logout = requests.post(baseURL + '/rest/logout', headers=header,
                       cookies=cookies, verify=verify)

# print script run time
dsFunc.elapsedTime(startTime, 'Script run time')

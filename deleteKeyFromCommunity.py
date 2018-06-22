import json
import requests
import secrets
import time
import csv
from datetime import datetime
import urllib3
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-k', '--deletedKey', help='the key to be deleted. optional - if not provided, the script will ask for input')
parser.add_argument('-i', '--handle', help='handle of the community to retreive. optional - if not provided, the script will ask for input')
args = parser.parse_args()

if args.deletedKey:
    deletedKey = args.deletedKey
else:
    deletedKey = raw_input('Enter the key to be deleted: ')

if args.handle:
    handle = args.handle
else:
    handle = raw_input('Enter collection handle: ')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

secretsVersion = raw_input('To edit production server, enter the name of the secrets file: ')
if secretsVersion != '':
    try:
        secrets = __import__(secretsVersion)
        print 'Editing Production'
    except ImportError:
        print 'Editing Stage'

baseURL = secrets.baseURL
email = secrets.email
password = secrets.password
filePath = secrets.filePath
verify = secrets.verify

startTime = time.time()
data = {'email':email,'password':password}
header = {'content-type':'application/json','accept':'application/json'}
session = requests.post(baseURL+'/rest/login', headers=header, verify=verify, params=data).cookies['JSESSIONID']
cookies = {'JSESSIONID': session}
headerFileUpload = {'accept':'application/json'}
cookiesFileUpload = cookies
status = requests.get(baseURL+'/rest/status', headers=header, cookies=cookies, verify=verify).json()
userFullName = status['fullname']
print 'authenticated'

endpoint = baseURL+'/rest/handle/'+handle
community = requests.get(endpoint, headers=header, cookies=cookies, verify=verify).json()
communityID = community['uuid']
collections = requests.get(baseURL+'/rest/communities/'+str(communityID)+'/collections', headers=header, cookies=cookies, verify=verify).json()
collSels = ''
for j in range (0, len (collections)):
    collectionID = collections[j]['uuid']
    collSel = '&collSel[]=' + collectionID
    collSels = collSels + collSel

f=csv.writer(open(filePath+'deletedValues'+datetime.now().strftime('%Y-%m-%d %H.%M.%S')+'.csv', 'wb'))
f.writerow(['handle']+['deletedValue']+['delete']+['post'])
offset = 0
recordsEdited = 0
items = ''
while items != []:
    endpoint = baseURL+'/rest/filtered-items?query_field[]='+deletedKey+'&query_op[]=exists&query_val[]='+collSels+'&limit=200&offset='+str(offset)
    print endpoint
    response = requests.get(endpoint, headers=header, cookies=cookies, verify=verify).json()
    items = response['items']
    for item in items:
        itemMetadataProcessed = []
        itemLink = item['link']
        print itemLink
        metadata = requests.get(baseURL + itemLink + '/metadata', headers=header, cookies=cookies, verify=verify).json()
        for l in range (0, len (metadata)):
            metadata[l].pop('schema', None)
            metadata[l].pop('element', None)
            metadata[l].pop('qualifier', None)
            languageValue = metadata[l]['language']
            if metadata[l]['key'] == deletedKey:
                provNote = '\''+deletedKey+'\' was deleted through a batch process on '+datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.'
                provNoteElement = {}
                provNoteElement['key'] = 'dc.description.provenance'
                provNoteElement['value'] = unicode(provNote)
                provNoteElement['language'] = 'en_US'
                itemMetadataProcessed.append(provNoteElement)
            else:
                itemMetadataProcessed.append(metadata[l])
        recordsEdited = recordsEdited + 1
        itemMetadataProcessed = json.dumps(itemMetadataProcessed)
        print 'updated', itemLink, recordsEdited
        delete = requests.delete(baseURL+itemLink+'/metadata', headers=header, cookies=cookies, verify=verify)
        print delete
        post = requests.put(baseURL+itemLink+'/metadata', headers=header, cookies=cookies, verify=verify, data=itemMetadataProcessed)
        print post
        f.writerow([itemLink]+[deletedKey]+[delete]+[post])
    offset = offset + 200
    print offset

logout = requests.post(baseURL+'/rest/logout', headers=header, cookies=cookies, verify=verify)

elapsedTime = time.time() - startTime
m, s = divmod(elapsedTime, 60)
h, m = divmod(m, 60)
print 'Total script run time: ', '%d:%02d:%02d' % (h, m, s)

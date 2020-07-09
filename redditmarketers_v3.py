# -*- coding: utf-8 -*-
import random  # Pretty much just for the state code
import json
import pandas as pd
from pandas.io.json import json_normalize
import praw  # Python Reddit API Wrapper, beats webscraping
import requests  # For OAuth and tokens and all that jazz
import requests.auth
import time # Debug purposes only
import sys
from prawcore import PrawcoreException
tStart = time.time()

# Initialise API variables
for iJustWantToHideThis in range(1):
    client_id = ""
    response_type = ""
    state = ""
    client_secret = ""
    username = ""
    password = ""
    user_agent = ""


    # Initialise API controller
    reddit = praw.Reddit(client_id=client_id, client_secret=client_secret,
                         password=password, user_agent=user_agent,
                         username=username)

# Define target user
target = "YOUR_TARGET_USER" # No u/ required

# Number of hops to extract
# 0 will extract only the target user. 
hops = 0

# Data layout hidden below
'''
{user: 'bob',
 posts: [
    {
     puid: relevant#
     title: 'posty',
     content: 'contenty',
     othedetail: 'blablabla'
     },
    {
     puid: relevant#2
     title: 'next piece',
     ...
     }
     ],
  comments: [
    {
      cuid: relevant#1,
      onPost: 'posty',
      content: 'bla bla bla'
    }
  ]
 }}
'''

users = {}
uPopCheck = False
processedPuids = []
extrdUsers = []
tracking = []  # Init tracking dictionary, see main process below


#####
# Class for users
#####
class User:
    def __init__(self, name):
        self.data = {
            'user': name,
            'posts': [],
            'comments': [],
            'procFlag': False,
            'extrFlag': False
        }

    def addPost(self, post):
        if 'puid' in post and 'title' in post and 'postText' in post and 'postLink' in post:
            self.data['posts'].append(post)
        else:
            print("Data not in correct format. Check puid, title, postText, and postLink keys are present.")

    def addComment(self, comment):
        if 'cuid' in comment and 'onPost' in comment and 'content' in comment:
            self.data['comments'].append(comment)
        else:
            print("Data not in correct format. Check cuid, onPost, and content keys are present.")

    def describe(self):
        print(self.data)


def makeUser(name):
    if not uPopCheck():
        users[name] = User(name)
    else:
        if name in list(users):  # Error check stage, check should happen during function call, this is a final catch
            print(f"{name} already exists; user not made.")
            print("If this is unexpected, restart the kernel.")
            print("Not restarting the kernel may lead to duplicated data.")
        else:
            # print(f"Making object: {name}")
            users[name] = User(name)


def uPopCheck():
    return len(users) != 0


def processUser(xtarget):
    print(f"Processing: {xtarget}")
    pStart = time.time()
    if uPopCheck() == True:
        if xtarget in list(users) and xtarget != target: # latter condition avoids trigger on first run
            print(f"{xtarget} already exists; user not processed.")
            print(f"Check for an existing entry with 'users[{xtarget}].describe()'")

        else:
            makeUser(xtarget)
            tPostIds = []
            tData = pd.DataFrame()

            collectPosts = reddit.redditor(xtarget).submissions.new()
            for post in collectPosts:
                tPost = {'user': xtarget,
                         # 'accAge': , # These will be added as a column later
                         # 'karma': ,
                         'isPoster': True,
                         'commentsJSON': None,
                         'puid': post.id,
                         'title': post.title,
                         'postText': post.selftext,
                         'postLink': post.url}
                tData.append(tPost, ignore_index=True)
                tPostIds.append(post.id)
                users[xtarget].addPost(tPost)

            collectComments = reddit.redditor(xtarget).comments.new()  # Stores locally to avoid multiple API calls
            for comment in collectComments:
                tComment = {'cuid': comment.id, 'onPost': comment.submission.id, 'content': comment.body}
                users[xtarget].addComment(tComment)

            for comment in users[xtarget].data['comments']:
                if comment['user'] == xtarget:
                    tData.loc[tData.loc[:, [tData['puid'] == comment['onPost'] & tData['user'] == xtarget]],
                              'commentsJSON'] = {'cuid': comment['cuid'],
                                                 'content': comment['content'] }

            users[xtarget].data['procFlag'] = True
    else:
        pass
    print(f"User took {time.time() - pStart}s to process\n")


def extractUsers(thelist): # The List is the main data dictionary
    tUsers = []  # Init place to store users found
    for pers in thelist:
        if pers not in extrdUsers:
            print(f"Extracting from: {pers}")
            eStart = time.time()
            # Posts extraction
            p = 0
            for aPost in thelist[pers].data['posts']:  # Existing logged users and their data
                if aPost not in processedPuids:
                    commentList = reddit.submission(id=aPost['puid']).comments
                    for aComment in commentList:
                        if aComment.parent_id[-6:] == aPost['puid']:  # Only take top-level comments
                            try:
                                tUsers.append(aComment.author)
                            except:
                                print(f"aComment from aPost not appended: {aComment} in {aPost}\n==========")
                p += 1
                processedPuids.append(aPost['puid'])
                print(f"\rPosts processed: {p}", end='')
            print("")

            # Comments extraction
            c = 0
            for bComment in thelist[pers].data['comments']:
                if bComment['onPost'] not in processedPuids:
                    try:
                        tUsers.append(reddit.submission(id=bComment['onPost']).author)
                        c += 1
                        processedPuids.append(bComment['onPost'])
                        print(f"\rComments processed: {c}", end='')
                    except:
                        print(f"bComment not appended: {bComment}\n")
            print("")
            print(f"User took {time.time() - eStart}s to extract from\n")
            extrdUsers.append(thelist[pers])
        else:
            pass
    # TODO Drop the user extracted from from Users dictionary
    return tUsers


def deduplicate(alist):
    blist = []
    for item in alist:
        if item not in blist:
            blist.append(item)  # Removes duplicates
    return blist


# Cycle through users
for i in range(hops + 1):
    print(f"Hop number: {i}")
    if i == 0:
        makeUser(target)  # Avoids problems on first loop
        processUser(target)
        tracking.append(target)

    else:
        userChecklist = []  # Init preprocess checklist
        for dawg in extractUsers(users):  # Extract users, add to tracking list
            if dawg == None:
                pass
            else:
                userChecklist.append(dawg.name)

            userChecklist = deduplicate(userChecklist)

            for u in userChecklist:
                if u in tracking:
                    pass
                else:
                    try:
                        processUser(u)
                    except PrawcoreException:
                        print(f"User '{u}' triggered a PRAW exception. They will not be processed and there will be no attempt to reprocess.")
                    tracking.append(u)  # We now know they've been processed, so they aren't reprocessed

Output = []
for u in users:
    Output.append(users[u].data)
with open('redmarData.json', 'w+') as f:
    json.dump(Output, f)

'''f = open("redmarData", 'w+')
writerData = []
for u in users:
    writerData.append(users[u].data)'

f.write(Output)
f.close()'''

# reddit.submission(id=users[XXXXXX].data['posts'][0]['puid']).comments[0].author.name

"""
The following code prints out the data for each user one by one. 
The logic used here is that each comment and post is only made once by a user.
Storing data like this helps ensure that each complete set of comments and posts are only recorded once.
"""

# Prints out the data for each user one by one
'''
import time
for acc in users:
  print(users[acc].describe())
  time.sleep(0.1)
'''

print(f"Total time to execute = {((time.time() - tStart) / 3600) - ((time.time() - tStart) % 3600)} hours and {(time.time() - tStart) % 60} minutes")
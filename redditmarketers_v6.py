import random  # Pretty much just for the state code
import pandas as pd
import praw  # Python Reddit API Wrapper, beats webscraping
import time  # Debug purposes only
import sys
import csv
from math import floor
from prawcore import PrawcoreException

# Initialise API variables
for iJustWantToHideThis in range(1):
    client_id = ""
    response_type = ""
    state = ""
    client_secret = ""
    username = ""
    password = ""
    user_agent = ""  # Do this when needed

    # Initialise API controller
    reddit = praw.Reddit(client_id=client_id, client_secret=client_secret,
                         password=password, user_agent=user_agent,
                         username=username)


class Loader:

    @staticmethod
    def appendToFile(linein, file):
        with open(file, 'a+') as f:
            w = csv.DictWriter(f, linein.keys())
            if f.tell() == 0:
                w.writeheader()
                w.writerow(linein)
            else:
                w.writerow(linein)

    @staticmethod
    def deduplicate(inlist):
        outlist = []
        for item in inlist:
            if item not in outlist:
                outlist.append(item)  # Removes duplicates
        return outlist

    @staticmethod
    def strClean(string):
        """Takes string, removes | and newlines, returns cleaned string."""
        string = string.replace("|", "[Pipe]")
        string = string.replace("\n", "[NewLine]")
        return string

    def processUser(self, user):
        # Returns a table of all the user's most recent posts and comments
        print(f"Processing: {user}")
        pStart = time.time()
        writeLim = 0

        # Only do this once per user being processed
        # Complete their user details
        try:
            redditUser = reddit.redditor(user)
            tUserData = {'Name': user,
                         'UserMade': redditUser.created_utc,
                         'LinkKarma': redditUser.link_karma,
                         'IsMod': redditUser.is_mod,
                         'CommentKarma': redditUser.comment_karma}
            self.appendToFile(tUserData, 'redmar_userData.csv')
            self.userListCompleted.append(user)
            tPostData = self.postData.loc[self.postData['Name'] == user, :]
            self.postData = self.postData.loc[self.postData['Name'] != user, :]
        except (AttributeError, MemoryError):
            print(f"DEBUG: {sys.exc_info()[0]}. USer was {user}.")
        except PrawcoreException:
            print(f"DEBUG: Prawcore exception occurred for user: {user}")

        collectPosts = reddit.redditor(user).submissions.new()  # Stores locally to avoid multiple API calls
        # We process submissions from the user one by one, first extracting their own post details
        try:
            for post in collectPosts:
                # print(f"Checking post: {post.id}")
                tSubmissionData = {'Subreddit': post.subreddit.display_name,
                                   'Puid': post.id,
                                   'Title': self.strClean(post.title),
                                   'URL': post.url,
                                   'TextLink': post.selftext}
                self.appendToFile(tSubmissionData, 'redmar_submissionData.csv')
                self.submissionHandled.append(post.id)

                # Then, we extract relevant comment authors from each post in turn
                for comment in post.comments:
                    try:
                        # print(f"Checking comment author: {comment.author.name}")
                        if comment.author.name not in self.userList:
                            self.userList.append(comment.author.name)
                            print(f"DEBUG: Added user from cuid: {comment.id}")
                        else:
                            pass
                    except (AttributeError, MemoryError):
                        print(f"DEBUG: {sys.exc_info()[0]}. Was the comment author None? Cuid: {comment.id}")
                    except PrawcoreException:
                        print(f"DEBUG: Prawcore exception occurred for comment id: {comment.id}")
        except (AttributeError, MemoryError):
            print(f"DEBUG: {sys.exc_info()[0]}. Did the user have no posts? User: {user}")
        except PrawcoreException:
            print(f"DEBUG: Prawcore exception occurred for user: {user}")

        collectComments = reddit.redditor(user).comments.new()  # Stores locally to avoid multiple API calls
        # First, process submissions via comments to add new posts (by their author) to DataFrame
        for comment in collectComments:
            # print(f"Handling comment: {comment.id}")
            if comment.submission.id not in self.submissionHandled:
                tSubmissionData = {'Subreddit': comment.submission.subreddit.display_name,
                                   'Puid': comment.submission.id,
                                   'Title': self.strClean(comment.submission.title),
                                   'URL': comment.submission.url,
                                   'TextLink': comment.submission.selftext}
                self.appendToFile(tSubmissionData, 'redmar_submissionData.csv')
                self.submissionHandled.append(comment.submission.id)
            # print("Add name to userData")
            try:
                if comment.submission.author.name not in self.userList:
                    self.userList.append(comment.submission.author.name)
                else:
                    pass

                # Now handle the comment itself and add it coherently to CommentsJSON
                if not tPostData.loc[tPostData['Puid'] == comment.submission.id, 'CommentsJSON'].empty:
                    existingComments = tPostData.loc[tPostData['Puid'] == comment.submission.id,
                                                     "CommentsJSON"].tolist()
                    existingComments.append(comment.id)
                    tPostData.loc[tPostData['Puid'] == comment.submission.id,
                                  "CommentsJSON"] = str(existingComments)
                    print(f"DEBUG: Added comments for cuid: {comment.submission.id}")
                else:
                    tPostData = tPostData.append({'Puid': comment.submission.id,
                                                  'Name': comment.author.name,
                                                  'IsPoster': comment.is_submitter,
                                                  'CommentsJSON': [comment.id]},
                                                 ignore_index=True)
            except (AttributeError, MemoryError):
                print(f"DEBUG: {sys.exc_info()[0]}. Was the submission author None? Puid: {comment.submission.id},"
                      f"from {comment.body}")
            except PrawcoreException:
                print(f"DEBUG: Prawcore exception occurred for comment id: {comment.id}")

        # Add in the new postData
        self.postData = self.postData.append(tPostData, ignore_index=True)
        print(f"User took {time.time() - pStart}s to process\n")


    def __init__(self, target, hops):
        self.userData = pd.DataFrame(columns=['Name', 'UserMade', 'LinkKarma', 'CommentKarma', 'IsMod'])
        self.postData = pd.DataFrame(columns=['Puid', 'Name', 'IsPoster', 'CommentsJSON'])
        self.submissionData = pd.DataFrame(columns=['Subreddit', 'Puid', 'Title', 'URL', 'TextLink'])
        self.userList = []
        self.userListCompleted = []
        self.submissionHandled = []
        # Initial target
        self.target = target
        # Number of hops to extract; 0 will extract only the target user.
        self.hops = hops

        # Initialise from our target
        self.userList.append(target)

        tStart = time.time()

        for i in range(hops + 1):
            print(f"Hop: {i} \n==============")
            userTempList = []
            for user in self.userList:
                userTempList.append(user)
            [self.processUser(user) if user not in self.userListCompleted else '' for user in userTempList]

        self.postData.to_csv('redmar_postData.csv')

        print(
            f"Total time to execute\n{floor(((time.time() - tStart) / 60) / 60)} hours, {floor(((time.time() - tStart) / 60) % 60)} minutes, and {floor((time.time() - tStart) % 60)} seconds")

#########
#########


Loader(target='YOUR_TARGET_USER', hops=1)

'''
This module contains logic to scrape the mountaineers web site using mtnscrape
and write to the database using mtndb.py (and SQLAlchemy directly).
'''
import pickle
import pathlib
import datetime
import time

from selenium import webdriver
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import object_session
from sqlalchemy.orm import Session

import mtnweb
import mtndb
import mtnschema
from enum import Enum


PROFILE_SCRAPE_INTERVAL = datetime.timedelta(days=7)

class TimeStatus(Enum):
    FUTURE = "future"
    CURRENT = "current"
    PAST = "past"

class Scrapester():

    def __init__(self, mtn_web: mtnweb.ScrapeMtnWeb, mtn_db: mtndb.MtnDB, username: str, password: str, session: Session | None = None):
        self.mtn_web = mtn_web
        self.mtn_db = mtn_db
        self.username = username
        self.password = password

        self._is_scrape_future = False
        self.mtn_person: mtnschema.Person | None = None

        if session:
            self._is_my_session = False
            self._session = session
        else:
            self._is_my_session = True
            self._session = mtn_db.session()

        self.mtn_person = mtn_db.person_find_by_username(self._session, self.username)
        self._session.commit()


    def close(self):
        if self._is_my_session:
            self._session.close()
        
        

    @property
    def is_scrape_future(self) -> bool:
        return self._is_scrape_future
    
    @is_scrape_future.setter
    def is_scrape_future(self, value: bool):
        self._is_scrape_future = value

    def login(self):
        self.mtn_web.login(self.username, self.password)

        is_scrape = self.mtn_person is None \
                        or self.mtn_person.last_scrapped is None \
                            or self.mtn_person.last_scrapped < datetime.datetime.now() - PROFILE_SCRAPE_INTERVAL
        if is_scrape:
            self._scrape_login_profile()




    def _scrape_login_profile(self):
        '''Scrape the profile of the currently logged in person/user.'''
        #
        # Go to their profile and scrape it.  
        #
        scraped_user = self.mtn_web.navigate_current_user_profile()
        if self.mtn_person is None:
            self.mtn_person = self._user_add(scraped_user, self.username, self.password)
        else:
            self._user_update(self.mtn_person, scraped_user)
        self._session.commit()


    def _user_add(self, scraped_user: mtnweb.ScrapedUser, username: str = "", password: str = "") -> mtnschema.Person:
        mtn_user = mtnschema.Person(profile_url=scraped_user.profile_url, 
                            user_name=username,
                            password=password,
                            full_name=scraped_user.full_name,
                            portrait_url=scraped_user.portrait_url,
                            email=scraped_user.email,
                            branch=scraped_user.branch,
                            is_scrapped=True,
                            last_scrapped=datetime.datetime.now())
        self.mtn_db.person_add(self._session, mtn_user)
        return mtn_user


    def _user_update(self, mtn_user: mtnschema.Person, scraped_user: mtnweb.ScrapedUser, username: str = "", password: str = "") -> mtnschema.Person:
        mtn_user.is_scrapped = True
        mtn_user.last_scrapped = datetime.datetime.now()
        mtn_user.profile_url = scraped_user.profile_url
        mtn_user.user_name = username
        # Don't store the password:  mtn_user.password = password
        mtn_user.full_name = scraped_user.full_name
        mtn_user.portrait_url = scraped_user.portrait_url
        mtn_user.email = scraped_user.email
        mtn_user.branch = scraped_user.branch
        return mtn_user


    def _find_update_user_by_profile(self, profile_url: str) -> mtnschema.Person:
        target_user = self.mtn_db.person_find_by_url(self._session, profile_url)

        is_scrape = target_user is None \
                        or target_user.last_scrapped is None \
                            or target_user.last_scrapped < datetime.datetime.now() - PROFILE_SCRAPE_INTERVAL
        if is_scrape:
            scraped_user = self.mtn_web.navigate_to_profile(profile_url)
            if target_user is None:
                target_user = self._user_add(scraped_user, self.username, self.password)
            else:
                self._user_update(target_user, scraped_user)

        return target_user



    @classmethod
    def _activity_calculate_next_scrape(cls, mtn_activity: mtnschema.Activity) -> datetime.datetime | None:
        delta: datetime.timedelta | None = None
        time_end = datetime.datetime.combine(mtn_activity.date_end, datetime.time(0,0,0))
        if mtn_activity.status == mtnweb.ACTIVITY_STATUS_FUTURE:
            # Future activities are scraped every 12 hours
            delta = datetime.timedelta(hours=12)
        elif mtn_activity.status == mtnweb.ACTIVITY_STATUS_PAST:
            # Past activities are scrapped in increasing intervals.
            # It might be closed eventually but then we give up.
            time_closed = datetime.datetime.now() - time_end
            if time_closed.days < 7:
                delta = datetime.timedelta(days=1)
            elif time_closed.days < 90:
                delta = datetime.timedelta(days=7)
            elif time_closed.days < 365:
                delta = datetime.timedelta(days=30)
            # More than 365 and we give up.
        else: # mtnscrape.ACTIVITY_STATUS_CLOSED
            time_closed = datetime.datetime.now() - time_end
            if time_closed.days < 7:
                # Initailly we check more often.  Double the time since close but at least 6 hours.
                delta = datetime.timedelta(seconds=max(60 * 60 * 6, 2 * time_closed.seconds))
                # Over 90 days we assume all changes are complete.
            elif time_closed.days < 90:
                # Within 90 days we still check for updates.
                delta = datetime.timedelta(days=21)
                # Over 90 days we assume all changes are complete.

        if delta:
            return datetime.datetime.now() + delta
        return None


    @classmethod
    def _time_status(cls, mtn_activity: mtnschema.Activity) -> TimeStatus:
        time_start = datetime.datetime.combine(mtn_activity.date_start, datetime.time(0,0,0))
        time_end = datetime.datetime.combine(mtn_activity.date_end, datetime.time(0,0,0)) + datetime.timedelta(days=1)
        time_now = datetime.datetime.now()

        if time_start > time_now:
            return TimeStatus.FUTURE
        if time_end < time_now:
            return TimeStatus.PAST
        return TimeStatus.CURRENT



    def _find_make_person_as_member(self, scp_activity_member: mtnweb.ScrapedActivityMember) -> mtnschema.Person:
        '''find an existing person or create a new one from the details that came from their participation in an activity.'''
        mtn_member_person = self.mtn_db.person_find_by_url(self._session, scp_activity_member.member_url)
        if not mtn_member_person:
            # Create a user with limited information and marking them as not yet scraped.
            mtn_member_person = mtnschema.Person(profile_url=scp_activity_member.member_url,
                                        user_name="",
                                        password="",
                                        full_name=scp_activity_member.member_name,
                                        portrait_url="",
                                        email="",
                                        branch="",
                                        is_scrapped=False,
                                        last_scrapped=None)
            self.mtn_db.person_add(self._session, mtn_member_person)
        return mtn_member_person
    


    def _activity_add(self, scp_activity: mtnweb.ScrapedActivity) -> mtnschema.Activity:
        #
        # Create the activity.
        #
        mtn_activity = mtnschema.Activity(date_start=scp_activity.date_start,
                                        date_end=scp_activity.date_end,
                                        name=scp_activity.name,
                                        activity_url=scp_activity.url,
                                        committee=scp_activity.committee,
                                        branch=scp_activity.branch,
                                        activity_type=scp_activity.activity_type,
                                        difficulty=scp_activity.difficulty,
                                        leader_rating=scp_activity.leader_rating,
                                        milage=scp_activity.milage,
                                        route_name=scp_activity.route_name,
                                        route_link=scp_activity.route_url,
                                        status=scp_activity.status,
                                        result=scp_activity.result,
                                        scrapped_at=datetime.datetime.now(),
                                        )
        mtn_activity.next_scrape = self._activity_calculate_next_scrape(mtn_activity)

        #
        # Create relationships for the participants
        #
        for scp_participant in scp_activity.participants:
            
            # Find the person
            mtn_member_person = self._find_make_person_as_member(scp_participant)

            # Add the person to the activity
            # Don't need to add new mtn_am to mtn_activity or mtn_member_user, because the relationship is bidirectional.
            mtn_am = mtnschema.ActivityMember(  # noqa: F841
                person=mtn_member_person,
                activity=mtn_activity,
                role=scp_participant.role,
                is_canceled=scp_participant.is_canceled,
                registration=scp_participant.registration,
                member_result=mtn_activity.result)
            self._session.add(mtn_am)
            print (f"  Added {mtn_member_person.full_name}")


        #
        # Add the activity to the database
        #
        self.mtn_db.activity_add(self._session, mtn_activity)



    def _activity_update(self, mtn_activity: mtnschema.Activity, scp_activity: mtnweb.ScrapedActivity) -> mtnschema.Activity:
        #
        # Update the activity.
        #
        mtn_activity.date_start = scp_activity.date_start
        mtn_activity.date_end = scp_activity.date_end
        mtn_activity.name = scp_activity.name
        mtn_activity.activity_url = scp_activity.url
        mtn_activity.committee = scp_activity.committee
        mtn_activity.branch = scp_activity.branch
        mtn_activity.activity_type = scp_activity.activity_type
        mtn_activity.difficulty = scp_activity.difficulty
        mtn_activity.leader_rating = scp_activity.leader_rating
        mtn_activity.milage = scp_activity.milage
        mtn_activity.route_name = scp_activity.route_name
        mtn_activity.route_link = scp_activity.route_url
        mtn_activity.status = scp_activity.status
        mtn_activity.result = scp_activity.result
        mtn_activity.scrapped_at = datetime.datetime.now()
        mtn_activity.next_scrape = self._activity_calculate_next_scrape(mtn_activity)
        mtn_activity.scrape_error = ""
        mtn_activity.scrape_error_count = 0
        mtn_activity.scrape_error_time = None

        #
        # Edit the participant list
        #
        existing_am: list[mtnschema.ActivityMember] = []
        existing_am.extend(mtn_activity.member_list)
        for scp_participant in scp_activity.participants:
            
            # Find the person
            mtn_member_person = self._find_make_person_as_member(scp_participant)

            # Find the ActivityMember record
            mtn_am = self.mtn_db.activitymember_find(self._session, mtn_member_person.id, mtn_activity.id)
            if mtn_am:
                # Update the record
                mtn_am.role = scp_participant.role
                mtn_am.is_canceled = scp_participant.is_canceled
                mtn_am.registration = scp_participant.registration
                mtn_am.member_result = scp_participant.member_result
                existing_am.remove(mtn_am)
                print (f"  Updated {mtn_member_person.full_name}")
            else:
                # Add the person to the activity
                mtn_am = mtnschema.ActivityMember(
                    person=mtn_member_person,
                    activity=mtn_activity,
                    role=scp_participant.role,
                    is_canceled=scp_participant.is_canceled,
                    registration=scp_participant.registration,
                    member_result=mtn_activity.result)
                self._session.add(mtn_am)
                mtn_activity.member_list.append(mtn_am)
                print (f"  Added {mtn_member_person.full_name}")


        # Remove any remaining ActivityMember records
        for am in existing_am:
            self._session.delete(am)
            print (f"  Removed {am.person.full_name}")
        return mtn_activity



    def _activity_scrape(self, activity_link: str) -> mtnweb.ScrapedActivity:
        # Retry multiple times until load is complete.  Some errors may resolve with delay and retry.
        is_complete = False    
        try_count = 3
        while not is_complete:
            is_complete = True    # Assume success
            try_count -= 1
            try:
                td = self.mtn_web.get_trip_details(activity_link)
                return td
                

            except mtnweb.WebResponseException as e:
                # An error interacting with the site which might resolve on retry.
                print (f"  retryable error {e.page_link} item {e.message}.")
                if e.__context__:
                    print (f"    cause: {type(e.__context__)} : {e.args}") 
                if try_count == 0:
                    raise
            
                # traceback.print_exc()
                is_complete = False
                delay = e.delay_seconds if e.delay_seconds else 60
                print (f"  Will retry in {delay} seconds")
                time.sleep(delay)

            except TimeoutError as e:
                print (f"  timeout on {activity_link} item {e.args}.")
                if try_count == 0:
                    raise
                print ("  Will retry")

            time.sleep(20)

        return None





    def _find_activity_member_by_url(self, activity_url: str) -> mtnschema.ActivityMember | None:
        for am in self.mtn_person.activity_list:
            if am.activity.activity_url == activity_url:
                return am
        return None






    def activity_update(self, mtn_activity: mtnschema.Activity):
        #
        # Find the trip in our database.
        #
 

        scp_activity = self._activity_scrape(mtn_activity.activity_url)
        try:
            self._activity_update(mtn_activity, scp_activity)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise e





    def scrape_activity_for_profile(self, profile_url: str = ""):
     

        if not profile_url:
            profile_url = self.mtn_person.profile_url

        # Always find the person within the current session.  
        # (using self.mtn_user may create a new record)
        target_person = self._find_update_user_by_profile(profile_url)
        self._session.commit()

        

        #
        # Get the person's trip list.
        #
        scp_member_activity_list = self.mtn_web.scrape_member_activities(target_person.profile_url)


        for scp_am in scp_member_activity_list:
            #
            # Find the activity
            #
            mtn_activity = self.mtn_db.activity_find_by_url(self._session, scp_am.activity_url)

            if mtn_activity:
                time_status = self._time_status(mtn_activity)
                if scp_am.is_canceled:
                    mtn_activity_member = self._find_activity_member_by_url(scp_am.activity_url)
                    if mtn_activity_member in target_person.activity_list:
                        print(f"{scp_am.registration}: {scp_am.activity_url}")
                        target_person.activity_list.remove(mtn_activity_member)
                        self._session.delete(mtn_activity_member)
                        print ("  Canceled from activity")
                else:
                    # Exists, check if it needs to be updated.
                    is_scrape = (mtn_activity.next_scrape is not None and mtn_activity.next_scrape <= datetime.datetime.now()) \
                                    or (self._is_scrape_future and time_status == TimeStatus.FUTURE)
                    if is_scrape:
                        print(f"{scp_am.registration}: {scp_am.activity_url}")
                        print("  Updating")
                        try:
                            scp_activity = self._activity_scrape(scp_am.activity_url)
                            if scp_activity is not None:
                                self._activity_update(mtn_activity, scp_activity)
                        except mtnweb.WebResponseException as e:
                            print (f"  scrape error {e.page_link} item {e.message}.")
                            if e.__context__:
                                print (f"    cause: {type(e.__context__)} : {e.args}")   
                            raise         
                            # TODO: else some record of the failure, retry later, and notify.
                    # else - not yet time to update
            else:
                if scp_am.is_canceled:
                    # No action on canceled activity that is not in the database.
                    pass
                else:
                    print(f"{scp_am.registration}: {scp_am.activity_url}")
                    print ("  Creating")    
                    try:
                        scp_activity = self._activity_scrape(scp_am.activity_url)
                        if scp_activity:
                            print (f"  {scp_activity.name}: {scp_activity.status} {scp_activity.result}")
                            mtn_activity = self._activity_add(scp_activity)
                    except mtnweb.WebResponseException as e:
                        print (f"  scrape error {e.page_link} item {e.message}.")
                        if e.__context__:
                            print (f"    cause: {type(e.__context__)} : {e.args}") 
                        raise             
                        # TODO: else some record of the failure, retry later, and notify.
            self._session.commit()

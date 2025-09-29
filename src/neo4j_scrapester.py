'''
This module contains logic to scrape the mountaineers web site using mtnweb
and write to the Neo4j database using neo4j_db.py.
Neo4j version of scrapester.py - replaces SQLAlchemy with graph database.
'''
import datetime
import time
import hashlib
from enum import Enum

import mtnweb
import neo4j_db


PROFILE_SCRAPE_INTERVAL = datetime.timedelta(days=7)

class TimeStatus(Enum):
    FUTURE = "future"
    CURRENT = "current"
    PAST = "past"

class Neo4jScrapester():
    """Neo4j version of Scrapester - replaces SQLAlchemy with graph database."""

    def __init__(self, mtn_web: mtnweb.ScrapeMtnWeb, neo_db: neo4j_db.Neo4jDB, username: str, password: str):
        self.mtn_web = mtn_web
        self.neo_db = neo_db
        self.username = username
        self.password = password

        self._is_scrape_future = False
        self.mtn_person: neo4j_db.Person | None = None

        # Find the logged-in user
        self.mtn_person = self.neo_db.person_find_by_username(self.username)

    def close(self):
        # Neo4j connections are managed by context manager
        pass

    @property
    def is_scrape_future(self) -> bool:
        return self._is_scrape_future
    
    @is_scrape_future.setter
    def is_scrape_future(self, value: bool):
        '''Set a flag to scrape all future events, regardless of their last scrape time.'''
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
        hashedpw = hashlib.sha256(self.password.encode("utf-8")).hexdigest()
        scraped_user = self.mtn_web.navigate_current_user_profile()
        
        if self.mtn_person is None:
            self.mtn_person = self._user_add(scraped_user, self.username, hashedpw)
        else:
            self._user_update(self.mtn_person, scraped_user, self.username, hashedpw)

    def _user_add(self, scraped_user: mtnweb.ScrapedUser, username: str = "", password: str = "") -> neo4j_db.Person:
        mtn_user = neo4j_db.Person(
            profile_url=scraped_user.profile_url, 
            user_name=username,
            password=password,
            full_name=scraped_user.full_name,
            portrait_url=scraped_user.portrait_url,
            email=scraped_user.email,
            branch=scraped_user.branch,
            is_scrapped=True,
            last_scrapped=datetime.datetime.now()
        )
        return self.neo_db.person_create(mtn_user)

    def _user_update(self, mtn_user: neo4j_db.Person, scraped_user: mtnweb.ScrapedUser, username: str = "", password: str = "") -> neo4j_db.Person:
        mtn_user.is_scrapped = True
        mtn_user.last_scrapped = datetime.datetime.now()
        mtn_user.profile_url = scraped_user.profile_url
        if username:
            mtn_user.user_name = username
        if password:
            mtn_user.password = password
        mtn_user.full_name = scraped_user.full_name
        mtn_user.portrait_url = scraped_user.portrait_url
        mtn_user.email = scraped_user.email
        mtn_user.branch = scraped_user.branch
        return self.neo_db.person_update(mtn_user)

    def _find_update_user_by_profile(self, profile_url: str) -> neo4j_db.Person:
        target_user = self.neo_db.person_find_by_url(profile_url)

        is_scrape = target_user is None \
                        or target_user.last_scrapped is None \
                            or target_user.last_scrapped < datetime.datetime.now() - PROFILE_SCRAPE_INTERVAL
        if is_scrape:
            scraped_user = self.mtn_web.navigate_to_profile(profile_url)
            if target_user is None:
                target_user = self._user_add(scraped_user, "", "")
            else:
                self._user_update(target_user, scraped_user)

        return target_user

    @classmethod
    def _activity_calculate_next_scrape(cls, mtn_activity: neo4j_db.Activity) -> datetime.datetime | None:
        delta: datetime.timedelta | None = None
        time_end = datetime.datetime.combine(mtn_activity.date_end, datetime.time(0,0,0))
        if mtn_activity.status == mtnweb.ACTIVITY_STATUS_FUTURE:
            # Future activities are scraped every 12 hours
            delta = datetime.timedelta(hours=12)
        elif mtn_activity.status == mtnweb.ACTIVITY_STATUS_PAST:
            # Past activities are scrapped in increasing intervals.
            time_closed = datetime.datetime.now() - time_end
            if time_closed.days < 7:
                delta = datetime.timedelta(days=1)
            elif time_closed.days < 90:
                delta = datetime.timedelta(days=7)
            elif time_closed.days < 365:
                delta = datetime.timedelta(days=30)
            # More than 365 and we give up.
        else: # mtnweb.ACTIVITY_STATUS_CLOSED
            time_closed = datetime.datetime.now() - time_end
            if time_closed.days < 7:
                delta = datetime.timedelta(seconds=max(60 * 60 * 6, 2 * time_closed.seconds))
            elif time_closed.days < 90:
                delta = datetime.timedelta(days=21)
                # Over 90 days we assume all changes are complete.

        if delta:
            return datetime.datetime.now() + delta
        return None

    @classmethod
    def _time_status(cls, mtn_activity: neo4j_db.Activity) -> TimeStatus:
        time_start = datetime.datetime.combine(mtn_activity.date_start, datetime.time(0,0,0))
        time_end = datetime.datetime.combine(mtn_activity.date_end, datetime.time(0,0,0)) + datetime.timedelta(days=1)
        time_now = datetime.datetime.now()

        if time_start > time_now:
            return TimeStatus.FUTURE
        if time_end < time_now:
            return TimeStatus.PAST
        return TimeStatus.CURRENT

    def _find_make_person_as_member(self, scp_activity_member: mtnweb.ScrapedActivityMember) -> neo4j_db.Person:
        '''Find an existing person or create a new one from the details that came from their participation in an activity.'''
        mtn_member_person = self.neo_db.person_find_by_url(scp_activity_member.member_url)
        if not mtn_member_person:
            # Create a user with limited information and marking them as not yet scraped.
            mtn_member_person = neo4j_db.Person(
                profile_url=scp_activity_member.member_url,
                user_name="",
                password="",
                full_name=scp_activity_member.member_name,
                portrait_url="",
                email="",
                branch="",
                is_scrapped=False,
                last_scrapped=None
            )
            mtn_member_person = self.neo_db.person_create(mtn_member_person)
        return mtn_member_person

    def _activity_add(self, scp_activity: mtnweb.ScrapedActivity) -> neo4j_db.Activity:
        # Create the activity
        mtn_activity = neo4j_db.Activity(
            date_start=scp_activity.date_start,
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

        # Create the activity node
        mtn_activity = self.neo_db.activity_create(mtn_activity)

        # Create relationships for the participants
        for scp_participant in scp_activity.participants:
            # Find the person
            mtn_member_person = self._find_make_person_as_member(scp_participant)

            # Create participation relationship
            participation = neo4j_db.Participation(
                role=scp_participant.role,
                is_canceled=scp_participant.is_canceled,
                registration=scp_participant.registration,
                member_result=mtn_activity.result
            )
            self.neo_db.create_participation(mtn_member_person, mtn_activity, participation)
            print(f"  Added {mtn_member_person.full_name}")

        return mtn_activity

    def _activity_update(self, mtn_activity: neo4j_db.Activity, scp_activity: mtnweb.ScrapedActivity) -> neo4j_db.Activity:
        # Update the activity properties
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

        # Update the activity node
        self.neo_db.activity_update(mtn_activity)

        # Get current participants
        current_participants = self.neo_db.get_activity_participants(mtn_activity)
        current_participant_urls = {person.profile_url: (person, participation) 
                                   for person, participation in current_participants}

        # Process scraped participants
        for index, scp_participant in enumerate(scp_activity.participants):
            # Find the person
            mtn_member_person = self._find_make_person_as_member(scp_participant)

            if mtn_member_person.profile_url in current_participant_urls:
                # Update existing participation
                _, existing_participation = current_participant_urls[mtn_member_person.profile_url]
                updated_participation = neo4j_db.Participation(
                    role=scp_participant.role,
                    is_canceled=scp_participant.is_canceled,
                    registration=scp_participant.registration,
                    member_result=scp_participant.member_result
                )
                self.neo_db.update_participation(mtn_member_person, mtn_activity, updated_participation)
                # Remove from current list so we know it was processed
                del current_participant_urls[mtn_member_person.profile_url]
                print(f"  {index+1:>2}: {mtn_member_person.full_name} - {scp_participant.role}")
            else:
                # Add new participation
                participation = neo4j_db.Participation(
                    role=scp_participant.role,
                    is_canceled=scp_participant.is_canceled,
                    registration=scp_participant.registration,
                    member_result=mtn_activity.result
                )
                self.neo_db.create_participation(mtn_member_person, mtn_activity, participation)
                print(f"  {index+1:>2}: {mtn_member_person.full_name} - {scp_participant.role} - Added")

        # Remove any remaining participants that are no longer in the activity
        for person_url, (person, participation) in current_participant_urls.items():
            self.neo_db.remove_participation(person, mtn_activity)
            print(f"  {person.full_name} - Removed")

        return mtn_activity

    def _activity_scrape(self, activity_link: str) -> mtnweb.ScrapedActivity:
        # Retry multiple times until load is complete
        is_complete = False    
        try_count = 3
        while not is_complete:
            is_complete = True    # Assume success
            try_count -= 1
            try:
                td = self.mtn_web.get_trip_details(activity_link)
                return td

            except mtnweb.WebResponseException as e:
                print(f"  retryable error {e.page_link} item {e.message}.")
                if e.__context__:
                    print(f"    cause: {type(e.__context__)} : {e.args}") 
                if try_count == 0:
                    raise
            
                is_complete = False
                delay = e.delay_seconds if e.delay_seconds else 60
                print(f"  Will retry in {delay} seconds")
                time.sleep(delay)

            except TimeoutError as e:
                print(f"  timeout on {activity_link} item {e.args}.")
                if try_count == 0:
                    raise
                print("  Will retry")

            time.sleep(20)

        return None

    def _find_activity_participation_by_url(self, activity_url: str) -> tuple[neo4j_db.Activity, neo4j_db.Participation] | None:
        """Find activity and participation for the logged-in user by activity URL."""
        if not self.mtn_person:
            return None
            
        # Get all activities for the person
        activities_with_participation = self.neo_db.get_person_activities(self.mtn_person)
        for activity, participation in activities_with_participation:
            if activity.activity_url == activity_url:
                return activity, participation
        return None

    def activity_update(self, mtn_activity: neo4j_db.Activity):
        """Update an existing activity by scraping its current state."""
        scp_activity = self._activity_scrape(mtn_activity.activity_url)
        try:
            self._activity_update(mtn_activity, scp_activity)
        except Exception as e:
            print(f"Error updating activity: {e}")
            raise e

    def scrape_person_activity(self, profile_url: str = ""):
        """
        Scrape a person's activity list.  

        Args:
            profile_url (str, optional): Optionally, the URL of a profile to scrape
            If not given, the login user's profile is scraped. Defaults to "".
        """

        if not profile_url:
            profile_url = self.mtn_person.profile_url

        # Find or update the target person
        target_person = self._find_update_user_by_profile(profile_url)

        # Get the person's trip list from the website
        scp_member_activity_list = self.mtn_web.scrape_member_activities(target_person.profile_url)

        for scp_am in scp_member_activity_list:
            # Find the activity in Neo4j
            mtn_activity = self.neo_db.activity_find_by_url(scp_am.activity_url)

            if mtn_activity:
                time_status = self._time_status(mtn_activity)
                if scp_am.is_canceled:
                    # Remove the participation if it exists
                    existing_participation = self.neo_db.find_participation(target_person, mtn_activity)
                    if existing_participation:
                        print(f"{scp_am.registration}: {scp_am.activity_url} - {mtn_activity.date_start}")
                        self.neo_db.remove_participation(target_person, mtn_activity)
                        print("  Canceled from activity")
                else:
                    # Check if it needs to be updated
                    is_scrape = (mtn_activity.next_scrape is not None and mtn_activity.next_scrape <= datetime.datetime.now()) \
                                    or (self._is_scrape_future and time_status == TimeStatus.FUTURE)
                    if is_scrape:
                        print(f"{scp_am.registration}: {scp_am.activity_url} - {mtn_activity.date_start}")
                        print("  Updating")
                        try:
                            scp_activity = self._activity_scrape(scp_am.activity_url)
                        except mtnweb.WebResponseException as e:
                            print(f"  scrape error {e.page_link} item {e.message}.")
                            if e.__context__:
                                print(f"    cause: {type(e.__context__)} : {e.args}") 
                            raise         
                        if scp_activity is not None:
                            self._activity_update(mtn_activity, scp_activity)
            else:
                if scp_am.is_canceled:
                    # No action on canceled activity that is not in the database.
                    pass
                else:
                    print(f"{scp_am.registration}: {scp_am.activity_url}")
                    print("  Creating")    
                    try:
                        scp_activity = self._activity_scrape(scp_am.activity_url)
                        if scp_activity:
                            print(f"  {scp_activity.name}: {scp_activity.status}, {scp_activity.date_start}, {scp_activity.result}")
                            mtn_activity = self._activity_add(scp_activity)
                    except mtnweb.WebResponseException as e:
                        print(f"  scrape error {e.page_link} item {e.message}.")
                        if e.__context__:
                            print(f"    cause: {type(e.__context__)} : {e.args}") 
                        raise             


# Legacy compatibility - keep original Scrapester class but add Neo4j option
class Scrapester():
    """Legacy Scrapester class - delegates to either SQLAlchemy or Neo4j implementation."""
    
    def __init__(self, mtn_web: mtnweb.ScrapeMtnWeb, mtn_db, username: str, password: str, session=None, use_neo4j: bool = False):
        if use_neo4j:
            # Use Neo4j implementation
            import neo4j_db
            neo_db = neo4j_db.Neo4jDB() if isinstance(mtn_db, neo4j_db.Neo4jDB) else neo4j_db.Neo4jDB()
            self._impl = Neo4jScrapester(mtn_web, neo_db, username, password)
        else:
            # Use original SQLAlchemy implementation - import the original scrapester
            import scrapester as original_scrapester
            self._impl = original_scrapester.Scrapester(mtn_web, mtn_db, username, password, session)
    
    def __getattr__(self, name):
        # Delegate all method calls to the implementation
        return getattr(self._impl, name)
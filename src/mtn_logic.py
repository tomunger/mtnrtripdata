"""
Business logic layer for mountaineer trip data.
Provides API for querying and managing trip data independent of UI/CLI.
"""
import datetime
import typing as t
from dataclasses import dataclass

import neo4j_db
import scrapester
import util


class MtnException(Exception):
    """Base exception for MountaineerLogic errors."""
    pass



@dataclass
class PersonInfo:
    """Person information for API responses."""
    profile_url: str
    user_name: str
    full_name: str
    portrait_url: str
    user_name: str
    email: str
    branch: str
    is_scrapped: bool
    last_scrapped: datetime.datetime | None


@dataclass
class ActivityInfo:
    """Activity information for API responses."""
    date_start: datetime.date
    date_end: datetime.date
    name: str
    activity_url: str
    activity_type: str
    committee: str = ""
    branch: str = ""
    difficulty: str = ""
    leader_rating: str = ""
    milage: str = ""
    route_name: str = ""
    route_link: str = ""
    status: str = ""
    result: str = ""
    scrapped_at: datetime.datetime | None = None
    next_scrape: datetime.datetime | None = None


@dataclass
class ParticipationInfo:
    """Participation information for API responses."""
    person: PersonInfo
    role: str
    is_canceled: bool = False
    registration: str = ""
    member_result: str = ""


@dataclass
class PersonActivityListInfo:
    """A person and the activities they were on"""
    shared_person: PersonInfo
    activites: list[ActivityInfo]


@dataclass
class ActivityWithInfo:
    """Information about shared activities between two people."""
    target_person: PersonInfo
    target_activities: list[ActivityInfo]
    shared: list[PersonActivityListInfo]


def _person_to_info(person: neo4j_db.Person | None) -> PersonInfo | None:
    """Convert Neo4j Person to PersonInfo."""
    if not person:
        return None
    return PersonInfo(
        profile_url=person.profile_url,
        user_name=person.user_name,
        full_name=person.full_name,
        portrait_url=person.portrait_url,
        email=person.email,
        branch=person.branch,
        is_scrapped=person.is_scrapped,
        last_scrapped=person.last_scrapped
    )


def _participation_to_info(participation: neo4j_db.Participation | None) -> ParticipationInfo | None:
    """Convert Neo4j Participation to ParticipationInfo."""
    if not participation:
        return None
    return ParticipationInfo(
        person=_person_to_info(participation.person),
        role=participation.role,
        is_canceled=participation.is_canceled,
        registration=participation.registration,
        member_result=participation.member_result
    )

def _activity_to_info(activity: neo4j_db.Activity | None) -> ActivityInfo | None:
    """Convert Neo4j Activity to ActivityInfo."""
    if not activity:
        return None
    return ActivityInfo(
        date_start=activity.date_start,
        date_end=activity.date_end,
        name=activity.name,
        activity_url=activity.activity_url,
        activity_type=activity.activity_type,
        committee=activity.committee,
        branch=activity.branch,
        difficulty=activity.difficulty,
        leader_rating=activity.leader_rating,
        milage=activity.milage,
        route_name=activity.route_name,
        route_link=activity.route_link,
        status=activity.status,
        result=activity.result,
        scrapped_at=activity.scrapped_at,
        next_scrape=activity.next_scrape
    )


class MountaineerLogic:
    """Business logic for mountaineer trip data operations."""
    
    def __init__(self, neo_db: neo4j_db.Neo4jDB):
        """Initialize with a Neo4j database connection."""
        self.neo_db = neo_db
    

    def person_by_username(self, username: str) -> PersonInfo | None:
        """Find a person by username."""
        person = self.neo_db.person_by_username(username)
        return _person_to_info(person) if person else None
    

    def person_by_profile_url(self, profile_url: str) -> PersonInfo | None:
        """Find a person by profile URL."""
        person = self.neo_db.person_by_url(profile_url)
        return _person_to_info(person) if person else None


    def persons_due_scrape(self, cutoff_date: datetime.date) -> list[PersonInfo]:
        """Get list of people due for scraping based on cutoff date."""
        persons = self.neo_db.persons_due_scrape(cutoff_date)
        return [_person_to_info(p) for p in persons]   

    def get_activities_on_date(self, person_info: PersonInfo, target_date: datetime.date) -> list[ActivityInfo]:
        """Get all activities for a person on a specific date."""
        person = self.neo_db.person_by_url(person_info.profile_url)
        if not person:
            return []
        
        activities = self.neo_db.activities_on_person_date(person, target_date)
        return [_activity_to_info(a) for a in activities]
    

    def get_shared_activities(self, person1_info: PersonInfo, person2_info: PersonInfo) -> list[ActivityInfo]:
        """Get all activities shared between two people."""
        person1 = self.neo_db.person_by_url(person1_info.profile_url)
        person2 = self.neo_db.person_by_url(person2_info.profile_url)
        
        if not person1 or not person2:
            return []
        
        activities = self.neo_db.get_shared_activities(person1, person2)
        return [_activity_to_info(a) for a in activities]
    

    def _db_activities_by_phrase(self,
            person: neo4j_db.Person,
            phrase: str
            ) -> list[neo4j_db.Activity]:
        phrase_lower = phrase.lower()
        activities_with_participation = self.neo_db.activity_part_by_person(person)
        
        matching_activities = []
        for activity, _ in activities_with_participation:
            if phrase_lower in activity.name.lower():
                matching_activities.append(activity)
        
        return matching_activities 
        


    def find_activities_by_date_and_phrase(
        self, 
        target_date: datetime.date, 
        phrase: str
    ) -> list[ActivityInfo]:
        """
        Find activities on a specific date that match a phrase in the name.
        
        Args:
            target_date: The date to search for activities
            phrase: Phrase to search for in activity names (case-insensitive)
            
        Returns:
            List of ActivityInfo objects matching the criteria
        """
        activities = self.neo_db.activities_by_date_and_phrase(target_date, phrase)
        return [_activity_to_info(a) for a in activities]
    
    
        
    def _db_person_find_by_url_name_user(
            self,
            url_name_user: str
        ) -> neo4j_db.Person | None:
        """Find a neo4j_db.Person by profile URL, name, or username.
        Args:
            url_name_user: Profile URL, full name, or username of the person
        Returns:
            neo_db.Person if found
        raises:
            MtnException if person not found.
        """

        # First, try to find the person by URL
        person = self.neo_db.person_by_url(url_name_user)
        if person:
            return person

        persons = self.neo_db.persons_by_name(url_name_user)
        if persons:
            if len(persons) > 1:
                raise MtnException(f"Multiple people found by name {url_name_user}.")
            return persons[0]

        person = self.neo_db.person_by_username(url_name_user)
        if person:
            return person
        raise MtnException(f"Person not found by URL, name, or username: {url_name_user}")




    def get_activity_details(self, activity_info: ActivityInfo) -> tuple[ActivityInfo, list[ParticipationInfo]]:
        """Get detailed information about an activity including participants."""
        activity = self.neo_db.activity_by_url(activity_info.activity_url)
        if not activity:
            return activity_info, []
        
        participants = self.neo_db.person_part_by_activity(activity)
        participation_list = []
        
        for person, participation in participants:
            participation_list.append(ParticipationInfo(
                person=_person_to_info(person),
                role=participation.role,
                is_canceled=participation.is_canceled,
                registration=participation.registration,
                member_result=participation.member_result
            ))
        
        return _activity_to_info(activity), participation_list


    def get_person_activity_history(self, url_name_user: str) -> list[ActivityInfo]:
        """Get the full activity history for a person."""
        target_person = self._db_person_find_by_url_name_user(url_name_user)
        activity_part_list = self.neo_db.activity_part_by_person(target_person)
        return [(_activity_to_info(activity), _participation_to_info(participation)) for activity, participation in activity_part_list]


    def who_with(
        self,
        url_name_user: str,
        activity_date: datetime.date
    ) -> list[ActivityWithInfo]:
        
        # Get the target person 
        target_person = self._db_person_find_by_url_name_user(url_name_user)

        # Get all their activities on the date.  Usually one but could be overlapping if a gathering or meeting.
        activity_list = self.neo_db.activities_on_person_date(target_person, activity_date)

        awi = ActivityWithInfo(target_person=target_person, target_activities=activity_list, shared = [])

        shared_person_map: dict[str, neo4j_db.Person] = {}
        for activity in activity_list:
            for person, participation in self.neo_db.person_part_by_activity(activity):
                if person.profile_url != target_person.profile_url:
                    shared_person_map[person.profile_url] = person

        for co_participant in shared_person_map.values():
            shared_activities = self.neo_db.get_shared_activities(target_person, co_participant)
            awi.shared.append(PersonActivityListInfo(co_participant,activites=shared_activities))
        
        return awi




    def did_do(
        self,
        url_name_user: str | None,
        trip_phrase: str
    ) -> list[ActivityInfo]:
        """
        Search for activities containing a phrase, optionally filtered by person.
        
        Args:
            trip_phrase: Phrase to search for in activity names (case-insensitive)
            url_name_user: Person's profile URL, full name, or username.

        Raises:
            MtnException: If the specified person is not found.
        Returns:
            List of ActivityInfo objects matching the criteria
        """
        target_person = self._db_person_find_by_url_name_user(url_name_user)
        matching_activities = self._db_activities_by_phrase(target_person, trip_phrase)   
        return [_activity_to_info(activity) for activity in matching_activities]


    def did_when(
        self,
        url_name_user: str | None,
        date: datetime.date
    ) -> list[ActivityInfo]:
        """
        Search for activities on a specific date, optionally filtered by person.
        
        Args:
            date: The date to search for activities
            url_name_user: Person's profile URL, full name, or username.
        Raises:
            MtnException: If the specified person is not found.
        Returns:
            List of ActivityInfo objects matching the criteria
        """
        target_person = self._db_person_find_by_url_name_user(url_name_user)
        matching_activities = self.neo_db.activities_on_person_date(target_person, date)

        return [_activity_to_info(activity) for activity in matching_activities]



    def trip_status(self,
        username: str, 
        password: str,                    
        url_name_user: str,
        date: datetime.date,
        is_visible_browser: bool = False,
        is_update: bool = False,
        progress_callback: t.Callable[[str], None] | None = None
    ) -> tuple[PersonInfo, list[ActivityInfo]]:
        """
        Get trip status for a person on a specific date.
        
        Args:
            url_name_user: Person's profile URL, full name, or username.
            date: The date of the trip
            is_update: Whether to update the trip information
        """
        target_person = self._db_person_find_by_url_name_user(url_name_user)
        activities = self.neo_db.activities_on_person_date(target_person, date)

        if is_update:
            with util.make_mtnweb(is_visible_browser) as mtn_web:
                scraper = scrapester.Neo4jScrapester(
                    mtn_web,
                    self.neo_db,
                    username,
                    password,
                    progress_callback=progress_callback
                )
                scraper.login()
                for activity in activities:
                    scraper.activity_update(activity)

            # Re-fetch activities after update
            activities = self.neo_db.activities_on_person_date(target_person, date)

        activity_infos = [_activity_to_info(activity) for activity in activities]
        return _person_to_info(target_person), activity_infos


    def scrape_person_activities(
        self, 
        username: str, 
        password: str,
        name_url_user: str = "",
        is_visible_browser: bool = False,
        force_scrape_future: bool = False,
        progress_callback: t.Callable[[str], None] | None = None
    ) -> dict[str, t.Any]:
        """
        Scrape activities for a person.
        
        Args:
            username: Login username
            password: Login password
            profile_url: Optional profile URL to scrape (defaults to logged-in user)
            is_visible_browser: Whether to show the browser window
            force_scrape_future: Force scrape all future activities
            progress_callback: Optional callback for progress messages
            
        Returns:
            Dictionary with scrape results including status and any errors
        """


        target_person = self._db_person_find_by_url_name_user(name_url_user)
        results = {
            "status": "success",
            "person": target_person.full_name,
            "errors": []
        }
        
        try:
            with util.make_mtnweb(is_visible=is_visible_browser) as mtn_web:
                scraper = scrapester.Neo4jScrapester(
                    mtn_web, 
                    self.neo_db, 
                    username, 
                    password,
                    progress_callback=progress_callback
                )
                scraper.is_scrape_future = force_scrape_future
                
                scraper.login()
                scraper.scrape_person_activity(profile_url=target_person.profile_url)
                
                results["status"] = "completed"
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))
        
        return results



    def update_activity(
        self,
        activity_info: ActivityInfo,
        username: str,
        password: str,
        progress_callback: t.Callable[[str], None] | None = None
    ) -> dict[str, t.Any]:
        """
        Update an activity by re-scraping it.
        
        Args:
            activity_info: Activity to update
            username: Login username
            password: Login password
            progress_callback: Optional callback for progress messages
            
        Returns:
            Dictionary with update results
        """
        results = {
            "status": "success",
            "activity_url": activity_info.activity_url,
            "errors": []
        }
        
        try:
            activity = self.neo_db.activity_by_url(activity_info.activity_url)
            if not activity:
                results["status"] = "error"
                results["errors"].append("Activity not found")
                return results
            
            with util.make_mtnweb() as mtn_web:
                scraper = scrapester.Neo4jScrapester(
                    mtn_web,
                    self.neo_db,
                    username,
                    password,
                    progress_callback=progress_callback
                )
                scraper.login()
                scraper.activity_update(activity)
                results["status"] = "completed"
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))
        
        return results

"""
Neo4j database module for mountaineer trip data.
Replaces SQLAlchemy implementation with graph database approach.
"""
import datetime
from dataclasses import dataclass, field, asdict
from neo4j import GraphDatabase, Driver, Session
import econfig



@dataclass
class Person:
    """A person who joins activities - Neo4j node representation."""
    profile_url: str = ""
    user_name: str = ""
    password: str = ""
    full_name: str = ""
    portrait_url: str = ""
    email: str = ""
    branch: str = ""
    prof_is_scrapped: bool = False
    prof_last_scrapped: datetime.datetime | None = None
    act_is_scrapped: bool = False
    act_last_scrapped: datetime.datetime | None = None
    
    # Neo4j internal ID (populated when loaded from database)
    _neo4j_id: int | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for Neo4j properties, excluding None values and internal fields."""
        data = {k: v for k, v in asdict(self).items() 
                if not k.startswith('_')}
        # Convert datetime to string for Neo4j storage
        for key in ['prof_last_scrapped', 'act_last_scrapped']:
            if key in data:
                data[key] = data[key].isoformat() if data[key] else ""
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Person':
        """Create Person from Neo4j node properties."""
        # Convert datetime string back to datetime object
        for key in ['prof_last_scrapped', 'act_last_scrapped']:
            if key in data:
                data[key] = datetime.datetime.fromisoformat(data[key]) if data[key] else None
        # Extract Neo4j ID if present
        neo4j_id = data.pop('_neo4j_id', None)
        person = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        person._neo4j_id = neo4j_id
        return person


@dataclass
class Activity:
    """An activity - Neo4j node representation."""
    date_start: datetime.date | None = None
    date_end: datetime.date | None = None
    name: str = ""
    activity_url: str = ""
    committee: str = ""
    branch: str = ""
    activity_type: str = ""
    difficulty: str = ""
    leader_rating: str = ""
    milage: str = ""
    route_name: str = ""
    route_link: str = ""
    status: str = ""
    result: str = ""
    scrapped_at: datetime.datetime | None = None
    next_scrape: datetime.datetime | None = None
    scrape_error: str = ""
    scrape_error_count: int = 0
    scrape_error_time: datetime.datetime | None = None
    
    # Neo4j internal ID (populated when loaded from database)
    _neo4j_id: int | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for Neo4j properties, excluding None values and internal fields."""
        data = {k: v for k, v in asdict(self).items() 
                if not k.startswith('_')}
        # Convert datetime/date objects to strings for Neo4j storage
        for key in ['date_start', 'date_end']:
            if key in data:
                # Store none as empty string.
                data[key] = data[key].isoformat() if data[key] else ""
        for key in ['scrapped_at', 'next_scrape', 'scrape_error_time']:
            if key in data:
                # Store None as empty string.
                data[key] = data[key].isoformat() if data[key] else ""
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Activity':
        """Create Activity from Neo4j node properties."""
        # Convert date strings back to date/datetime objects
        for key in ['date_start', 'date_end']:
            if key in data:
                data[key] = datetime.date.fromisoformat(data[key]) if data[key] else None
        for key in ['scrapped_at', 'next_scrape', 'scrape_error_time']:
            if key in data:
                # Convert to datetime.  Empty string becomes None.
                data[key] = datetime.datetime.fromisoformat(data[key]) if data[key] else None
        # Extract Neo4j ID if present
        neo4j_id = data.pop('_neo4j_id', None)
        activity = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        activity._neo4j_id = neo4j_id
        return activity


@dataclass
class Participation:
    """Represents a PARTICIPATE relationship between Person and Activity."""
    role: str = ""
    is_canceled: bool = False
    registration: str = ""
    member_result: str = ""
    person: Person | None = None
    activity: Activity | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Neo4j relationship properties."""
        return asdict(self)

    @classmethod
    def from_dict(cls, 
                  data: dict, 
                  person: Person | None = None,
                  activity: Activity | None = None
        ) -> 'Participation':
        """Create Participation from Neo4j relationship properties."""
        part = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        part.person = person
        part.activity = activity
        return part


class Neo4jDB:
    """Neo4j database interface for mountaineer trip data."""

    def __init__(self, driver: Driver = None):
        if driver is None:
            uri = econfig.get(econfig.NEO4J_URL)
            username = econfig.get(econfig.NEO4J_USERNAME)
            password = econfig.get(econfig.NEO4J_PASSWORD)
            if not all([uri, username, password]):
                raise ValueError("Neo4j credentials not found in environment")
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
        else:
            self.driver = driver


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


    def close(self):
        if self.driver:
            self.driver.close()


    def session(self) -> Session:
        """Create a new Neo4j session."""
        return self.driver.session()


    def create_constraints(self):
        """Create Neo4j constraints and indexes for better performance."""
        with self.session() as session:
            # Unique constraints
            session.run("CREATE CONSTRAINT person_profile_url IF NOT EXISTS FOR (p:Person) REQUIRE p.profile_url IS UNIQUE")
            session.run("CREATE CONSTRAINT activity_url IF NOT EXISTS FOR (a:Activity) REQUIRE a.activity_url IS UNIQUE")
            
            # Indexes for common queries
            session.run("CREATE INDEX person_username IF NOT EXISTS FOR (p:Person) ON (p.user_name)")
            session.run("CREATE INDEX person_fullname IF NOT EXISTS FOR (p:Person) ON (p.full_name)")
            session.run("CREATE INDEX activity_dates IF NOT EXISTS FOR (a:Activity) ON (a.date_start, a.date_end)")


    # Person operations
    def person_create(self, person: Person) -> Person:
        """Create a new Person node."""
        with self.session() as session:
            result = session.run(
                "CREATE (p:Person $props) RETURN p, elementId(p) as node_id",
                props=person.to_dict()
            )
            record = result.single()
            person._neo4j_id = record["node_id"]
            return person


    def person_by_url(self, profile_url: str) -> Person | None:
        """Find person by profile URL."""
        with self.session() as session:
            result = session.run(
                "MATCH (p:Person {profile_url: $url}) RETURN p, elementId(p) as node_id",
                url=profile_url
            )
            record = result.single()
            if record:
                data = dict(record["p"])
                data["_neo4j_id"] = record["node_id"]
                return Person.from_dict(data)
            return None



    def persons_by_name(self, full_name: str) -> list[Person]:
        """Find persons by full name (case-insensitive, partial match)."""
        persons = []
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)
                WHERE toLower(p.full_name) CONTAINS toLower($name)
                RETURN p, elementId(p) as person_id
                """,
                name=full_name
            )
            for record in result:
                person_data = dict(record["p"])
                person_data["_neo4j_id"] = record["person_id"]
                persons.append(Person.from_dict(person_data))
        return persons


    def person_by_username(self, username: str) -> Person | None:
        """Find person by username."""
        with self.session() as session:
            result = session.run(
                "MATCH (p:Person {user_name: $username}) RETURN p, elementId(p) as node_id",
                username=username
            )
            record = result.single()
            if record:
                data = dict(record["p"])
                data["_neo4j_id"] = record["node_id"]
                return Person.from_dict(data)
            return None


    def persons_act_due_scrape(self, cutoff_date: datetime.date, limit: int = 0) -> list[Person]:
        """Get list of people due to have their activities scrapped.
        Args:
            cutoff_date: Scrape all persons whose act_last_scrapped is on or before this date.

        Returns:
            list of Person objects due for activity scraping.

        """
        persons = []
        cutoff_str = cutoff_date.isoformat()
        with self.session() as session:
            query = """
            MATCH (p:Person)
            WHERE p.act_is_scrapped and p.act_last_scrapped <= $cutoff
            RETURN p, elementId(p) as person_id
            ORDER BY p.act_last_scrapped ASC
            """
            if limit > 0:
                query += " LIMIT $limit"
                result = session.run(query, cutoff=cutoff_str, limit=limit)
            else:
                result = session.run(query, cutoff=cutoff_str)
            
            for record in result:
                person_data = dict(record["p"])
                person_data["_neo4j_id"] = record["person_id"]
                persons.append(Person.from_dict(person_data))
        return persons


    def persons_with_act_scraped(self) -> list[Person]:
        """Get all people who have had their activities scraped (act_is_scrapped = True).
        
        Returns:
            list of Person objects with act_is_scrapped = True, unsorted
        """
        persons = []
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)
                WHERE p.act_is_scrapped = true
                RETURN p, elementId(p) as person_id
                """
            )
            
            for record in result:
                person_data = dict(record["p"])
                person_data["_neo4j_id"] = record["person_id"]
                persons.append(Person.from_dict(person_data))
        return persons



    def person_update(self, person: Person) -> Person:
        """Update an existing Person node."""
        if person._neo4j_id is None:
            raise ValueError("Cannot update person without Neo4j ID")
        
        with self.session() as session:
            session.run(
                "MATCH (p:Person) WHERE elementId(p) = $id SET p += $props",
                id=person._neo4j_id,
                props=person.to_dict()
            )
            return person


    def person_set_act_scrapped(self, person: Person, is_scrapped: bool) -> Person:
        """Set the act_is_scrapped flag for a person.
        
        Args:
            person: The person to update
            is_scrapped: The value to set for act_is_scrapped
            
        Returns:
            Updated Person object
        """
        if person._neo4j_id is None:
            raise ValueError("Cannot update person without Neo4j ID")
        
        with self.session() as session:
            session.run(
                "MATCH (p:Person) WHERE elementId(p) = $id SET p.act_is_scrapped = $is_scrapped",
                id=person._neo4j_id,
                is_scrapped=is_scrapped
            )
            person.act_is_scrapped = is_scrapped
            return person


    # Activity operations
    def activity_create(self, activity: Activity) -> Activity:
        """Create a new Activity node."""
        with self.session() as session:
            result = session.run(
                "CREATE (a:Activity $props) RETURN a, elementId(a) as node_id",
                props=activity.to_dict()
            )
            record = result.single()
            activity._neo4j_id = record["node_id"]
            return activity
    

    def activity_update(self, activity: Activity) -> Activity:
        """Update an existing Activity node."""
        if activity._neo4j_id is None:
            raise ValueError("Cannot update activity without Neo4j ID")
        
        with self.session() as session:
            session.run(
                "MATCH (a:Activity) WHERE elementId(a) = $id SET a += $props",
                id=activity._neo4j_id,
                props=activity.to_dict()
            )
            return activity


    def activity_by_url(self, activity_url: str) -> Activity | None:
        """Find activity by URL."""
        with self.session() as session:
            result = session.run(
                "MATCH (a:Activity {activity_url: $url}) RETURN a, elementId(a) as node_id",
                url=activity_url
            )
            record = result.single()
            if record:
                data = dict(record["a"])
                data["_neo4j_id"] = record["node_id"]
                return Activity.from_dict(data)
            return None


    def activities_by_date_and_phrase(
        self,
        target_date: datetime.date,
        phrase: str
    ) -> list[Activity]:
        """
        Find activities on a specific date that match a phrase in the name.
        
        Args:
            target_date: The date to search for activities
            phrase: Phrase to search for in activity names (case-insensitive)
            
        Returns:
            List of Activity objects matching the criteria
        """
        phrase_lower = phrase.lower()
        matching_activities = []
        
        with self.session() as session:
            # Cypher query to find activities on a specific date with phrase in name
            result = session.run(
                """
                MATCH (a:Activity)
                WHERE a.date_start <= $date AND a.date_end >= $date
                AND toLower(a.name) CONTAINS $phrase
                RETURN a, elementId(a) as activity_id
                ORDER BY a.date_start, a.name
                """,
                date=target_date.isoformat(),
                phrase=phrase_lower
            )
            
            for record in result:
                activity_data = dict(record["a"])
                activity_data["_neo4j_id"] = record["activity_id"]
                activity = Activity.from_dict(activity_data)
                matching_activities.append(activity)
        
        return matching_activities


    def activities_on_person_date(self, person: Person, target_date: datetime.date) -> list[Activity]:
        """Get all activities for a person on a specific date."""
        if person._neo4j_id is None:
            return []
        
        date_str = target_date.isoformat()
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)-[:PARTICIPATE]->(a:Activity)
                WHERE elementId(p) = $person_id 
                AND a.date_start <= $date AND a.date_end >= $date
                RETURN a, elementId(a) as activity_id
                ORDER BY a.date_start
                """,
                person_id=person._neo4j_id,
                date=date_str
            )
            activities = []
            for record in result:
                activity_data = dict(record["a"])
                activity_data["_neo4j_id"] = record["activity_id"]
                activities.append(Activity.from_dict(activity_data))
            return activities



    # Participation relationship operations
    def participation_create(self, person: Person, activity: Activity, participation: Participation):
        """Create a PARTICIPATE relationship between Person and Activity."""
        if person._neo4j_id is None or activity._neo4j_id is None:
            raise ValueError("Both person and activity must have Neo4j IDs")
        
        with self.session() as session:
            session.run(
                """
                MATCH (p:Person), (a:Activity) 
                WHERE elementId(p) = $person_id AND elementId(a) = $activity_id
                CREATE (p)-[:PARTICIPATE $props]->(a)
                """,
                person_id=person._neo4j_id,
                activity_id=activity._neo4j_id,
                props=participation.to_dict()
            )


    def participation_update(self, person: Person, activity: Activity, participation: Participation):
        """Update an existing PARTICIPATE relationship."""
        if person._neo4j_id is None or activity._neo4j_id is None:
            raise ValueError("Both person and activity must have Neo4j IDs")
        
        with self.session() as session:
            session.run(
                """
                MATCH (p:Person)-[r:PARTICIPATE]->(a:Activity)
                WHERE elementId(p) = $person_id AND elementId(a) = $activity_id
                SET r += $props
                """,
                person_id=person._neo4j_id,
                activity_id=activity._neo4j_id,
                props=participation.to_dict()
            )

    def participation_find(self, person: Person, activity: Activity) -> Participation | None:
        """Find existing participation relationship."""
        if person._neo4j_id is None or activity._neo4j_id is None:
            return None
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)-[r:PARTICIPATE]->(a:Activity)
                WHERE elementId(p) = $person_id AND elementId(a) = $activity_id
                RETURN r
                """,
                person_id=person._neo4j_id,
                activity_id=activity._neo4j_id
            )
            record = result.single()
            if record:
                return Participation.from_dict(dict(record["r"]), person = person, activity=activity)
            return None


    def participation_remove(self, person: Person, activity: Activity):
        """Remove a PARTICIPATE relationship."""
        if person._neo4j_id is None or activity._neo4j_id is None:
            return
        
        with self.session() as session:
            session.run(
                """
                MATCH (p:Person)-[r:PARTICIPATE]->(a:Activity)
                WHERE elementId(p) = $person_id AND elementId(a) = $activity_id
                DELETE r
                """,
                person_id=person._neo4j_id,
                activity_id=activity._neo4j_id
            )


    def activity_part_by_person(self, person: Person) -> list[tuple[Activity, Participation]]:
        """Get all activities and participation for a person.
        
        Args:
            person: Person object

        Returns:
            List of tuples (Activity, Participation)
        """
        if person._neo4j_id is None:
            return []
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)-[r:PARTICIPATE]->(a:Activity)
                WHERE elementId(p) = $person_id
                RETURN a, r, elementId(a) as activity_id
                ORDER BY a.date_start
                """,
                person_id=person._neo4j_id
            )
            activities = []
            for record in result:
                activity_data = dict(record["a"])
                activity_data["_neo4j_id"] = record["activity_id"]
                activity = Activity.from_dict(activity_data)
                participation = Participation.from_dict(dict(record["r"]), person=person, activity=activity)
                activities.append((activity, participation))
            return activities


    def person_part_by_activity(self, activity: Activity) -> list[tuple[Person, Participation]]:
        """Get all persons and their participation for an activity."""
        if activity._neo4j_id is None:
            return []
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)-[r:PARTICIPATE]->(a:Activity)
                WHERE elementId(a) = $activity_id
                RETURN p, r, elementId(p) as person_id
                ORDER BY p.full_name
                """,
                activity_id=activity._neo4j_id
            )
            participants = []
            for record in result:
                person_data = dict(record["p"])
                person_data["_neo4j_id"] = record["person_id"]
                person = Person.from_dict(person_data)
                participation = Participation.from_dict(dict(record["r"]), activity=activity, person=person)
                participants.append((person, participation))
            return participants

    def get_people_on_activities(self, activities: list[Activity]) -> dict[str, Person]:
        """Get all people who participated in any of the given activities."""
        if not activities:
            return {}
        
        activity_ids = [a._neo4j_id for a in activities if a._neo4j_id is not None]
        if not activity_ids:
            return {}
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)-[:PARTICIPATE]->(a:Activity)
                WHERE elementId(a) IN $activity_ids
                RETURN DISTINCT p, elementId(p) as person_id
                """,
                activity_ids=activity_ids
            )
            people = {}
            for record in result:
                person_data = dict(record["p"])
                person_data["_neo4j_id"] = record["person_id"]
                person = Person.from_dict(person_data)
                people[person.profile_url] = person
            return people


    def get_shared_activities(self, person1: Person, person2: Person) -> list[Activity]:
        """Get all activities that two people both participated in."""
        if person1._neo4j_id is None or person2._neo4j_id is None:
            return []
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p1:Person)-[:PARTICIPATE]->(a:Activity)<-[:PARTICIPATE]-(p2:Person)
                WHERE elementId(p1) = $person1_id AND elementId(p2) = $person2_id
                RETURN a, elementId(a) as activity_id
                ORDER BY a.date_start
                """,
                person1_id=person1._neo4j_id,
                person2_id=person2._neo4j_id
            )
            activities = []
            for record in result:
                activity_data = dict(record["a"])
                activity_data["_neo4j_id"] = record["activity_id"]
                activities.append(Activity.from_dict(activity_data))
            return activities
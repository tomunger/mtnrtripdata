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
    is_scrapped: bool = False
    last_scrapped: datetime.datetime | None = None
    
    # Neo4j internal ID (populated when loaded from database)
    _neo4j_id: int | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for Neo4j properties, excluding None values and internal fields."""
        data = {k: v for k, v in asdict(self).items() 
                if not k.startswith('_') and v is not None}
        # Convert datetime to string for Neo4j storage
        if 'last_scrapped' in data and data['last_scrapped']:
            data['last_scrapped'] = data['last_scrapped'].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Person':
        """Create Person from Neo4j node properties."""
        # Convert datetime string back to datetime object
        if 'last_scrapped' in data and data['last_scrapped']:
            data['last_scrapped'] = datetime.datetime.fromisoformat(data['last_scrapped'])
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
                if not k.startswith('_') and v is not None}
        # Convert datetime/date objects to strings for Neo4j storage
        for key in ['date_start', 'date_end']:
            if key in data and data[key]:
                data[key] = data[key].isoformat()
        for key in ['scrapped_at', 'next_scrape', 'scrape_error_time']:
            if key in data and data[key]:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Activity':
        """Create Activity from Neo4j node properties."""
        # Convert date strings back to date/datetime objects
        for key in ['date_start', 'date_end']:
            if key in data and data[key]:
                data[key] = datetime.date.fromisoformat(data[key])
        for key in ['scrapped_at', 'next_scrape', 'scrape_error_time']:
            if key in data and data[key]:
                data[key] = datetime.datetime.fromisoformat(data[key])
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
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Neo4j relationship properties."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Participation':
        """Create Participation from Neo4j relationship properties."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


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

    def person_find_by_url(self, profile_url: str) -> Person | None:
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

    def person_find_by_username(self, username: str) -> Person | None:
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

    def activity_find_by_url(self, activity_url: str) -> Activity | None:
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

    # Participation relationship operations
    def create_participation(self, person: Person, activity: Activity, participation: Participation):
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

    def find_participation(self, person: Person, activity: Activity) -> Participation | None:
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
                return Participation.from_dict(dict(record["r"]))
            return None

    def update_participation(self, person: Person, activity: Activity, participation: Participation):
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

    def remove_participation(self, person: Person, activity: Activity):
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

    # Query operations that replace SQLAlchemy join logic
    def get_person_activities(self, person: Person) -> list[tuple[Activity, Participation]]:
        """Get all activities for a person with their participation details."""
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
                participation = Participation.from_dict(dict(record["r"]))
                activities.append((activity, participation))
            return activities

    def get_activity_participants(self, activity: Activity) -> list[tuple[Person, Participation]]:
        """Get all participants for an activity with their participation details."""
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
                participation = Participation.from_dict(dict(record["r"]))
                participants.append((person, participation))
            return participants

    def get_activities_on_date(self, person: Person, target_date: datetime.date) -> list[Activity]:
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
import typing as t
import datetime

import mtnschema

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session





def trips_on_date(person: mtnschema.Person, trip_date: datetime.date) -> list[mtnschema.Activity]:
    trip_list = []
    for am in person.activity_list:
        a = am.activity
        if trip_date >= a.date_start and trip_date <= a.date_end:
            trip_list.append(a)
    return trip_list


def people_on_trips(trip_list: list[mtnschema.Activity]) -> dict[str, mtnschema.Person]:
    person_list: dict[str, mtnschema.Person] = {}
    for a in trip_list: 
        for am in a.member_list:
            u = am.person
            if u.profile_url not in person_list:
                person_list[u.profile_url] = u
    return person_list

class MtnDB():

    def __init__(self, engine: Engine):
        self.engine = engine
        self.metadata = mtnschema.Base.metadata
        pass

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
    
    def close(self):
        self.engine.dispose()

    def create_tables(self):
        mtnschema.Base.metadata.create_all(self.engine)

    def drop_tables(self):
        mtnschema.Base.metadata.drop_all(self.engine)

    def session(self) -> Session:
        s = Session(self.engine)
        # s.autoflush = False
        return s



    def person_find_by_url(self, session: Session, profile_url: str) -> mtnschema.Person | None:
        stmt = session.query(mtnschema.Person).filter(mtnschema.Person.profile_url == profile_url)
        result = session.execute(stmt)
        r = result.scalars().first()
        return r


    def person_find_by_username(self, session: Session, username: str) -> mtnschema.Person | None:
        stmt = session.query(mtnschema.Person).filter(mtnschema.Person.user_name == username)  
        result = session.execute(stmt)
        r = result.scalars().first()
        return r





    def select_person_by(self, session, profile_url: str, user_name: str) -> mtnschema.Person:
        """
        Selects a person from the database based on either profile_url or user_name.  
        profile_url takes precedence over user_name if both are provided.
        Args:
            session: The SQLAlchemy session to use for the query.
            profile_url (str): The profile URL of the person to select.
            user_name (str): The user name of the person to select.
        Returns:
            mtnschema.Person: The person object that matches the given profile_url or user_name.
        Raises:
            ValueError: If neither profile_url nor user_name is provided, or if the query does not return exactly one result.
        """

        stmt = select(mtnschema.Person)
        if profile_url:
            stmt = stmt.filter(mtnschema.Person.profile_url == profile_url)
        elif user_name:
            stmt = stmt.filter(mtnschema.Person.user_name == user_name)
        else:
            raise ValueError("Must provide either profile_url or user_name")
        result = session.execute(stmt).scalars().all()
        if len(result) != 1:
            raise ValueError(f"Expected 1 result, got {len(result)}")
        return result[0]


    def activity_find_by_url(self,  session: Session, activity_url: str) -> mtnschema.Activity | None:
        stmt = session.query(mtnschema.Activity).filter(mtnschema.Activity.activity_url == activity_url)
        result = session.execute(stmt)
        return result.scalars().first()
    
    def activitymember_find(self,  session: Session, person_id: int, activity_id: int) -> mtnschema.ActivityMember | None:
        stmt = session.query(mtnschema.ActivityMember).filter(mtnschema.ActivityMember.person_id == person_id).filter(mtnschema.ActivityMember.activity_id == activity_id)
        result = session.execute(stmt)
        return result.scalars().first()
        
    def person_add(self,  session: Session, person: mtnschema.Person):
        session.add(person)
        session.flush()

    def activity_add(self,  session: Session, activity: mtnschema.Activity):
        session.add(activity)
        session.flush()
        
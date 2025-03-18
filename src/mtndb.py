import typing as t

import mtnschema

from sqlalchemy import Engine
from sqlalchemy.orm import Session


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
        return Session(self.engine)

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

    def activity_add(self,  session: Session, activity: mtnschema.Activity):
        session.add(activity)
        
import typing as t
import datetime
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String, DateTime, Date
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


URL_LENGTH = 600
PERSON_NAME_LENGTH = 100
USER_NAME_LENGTH = 60
PASSWORD_LENGTH = 60
EMAIL_LENGTH = 200
BRANCH_LENGTH = 60
ROLE_LENGTH = 100
STATUS_LENGTH = 20
RESULT_LENGTH = 20
ACTIVITY_TYPE_LENGTH = 100
DIFFICULTY_LENGTH = 100
LEADER_RATING_LENGTH = 100
MILEAGE_LENGTH = 15
ROUTE_NAME_LENGTH = 100
COMMITTEE_LENGTH = 100
ROUTE_NAME_LENGTH = 200

ACTIVITY_STATUS_FUTURE = "FU"  # Future and currently happening
ACTIVITY_STATUS_PAST = "PA"    # Has happened but not closed so may change
ACTIVITY_STATUS_CLOSED = "CL"  # Closed and unlikely to change

class Base(DeclarativeBase):
    '''Define a base class for all the tables'''
    pass



class Person(Base):
    '''A person who joins activities.'''
    __tablename__ = "person"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_url: Mapped[str] = mapped_column(String(URL_LENGTH), default="", index=True)
    user_name: Mapped[str] = mapped_column(String(USER_NAME_LENGTH), default="", index=True)
    password: Mapped[str] = mapped_column(String(PASSWORD_LENGTH), default="")
    full_name: Mapped[str] = mapped_column(String(PERSON_NAME_LENGTH), default="", index=True)
    portrait_url: Mapped[str] = mapped_column(String(URL_LENGTH), default="")
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), default="")
    branch: Mapped[str] = mapped_column(String(BRANCH_LENGTH), default="")

    is_scrapped: Mapped[bool] = mapped_column(default=False)  
    last_scrapped: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None)

    activity_list: Mapped[t.List["ActivityMember"]] = relationship("ActivityMember", back_populates="person", 
                                                    cascade="all, delete, delete-orphan",
                                                    passive_deletes=True)


    def __repr__(self) -> str:
        return f"Person(id={self.id!r}, full_name={self.full_name!r})"


class ActivityMember(Base):
    '''A record of a person's participation in an activity.'''
    __tablename__ = "activitymember"
    id: Mapped[int] = mapped_column(primary_key=True)
    
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"))
    person: Mapped["Person"] = relationship("Person", back_populates="activity_list")                     # Who is on the activity
    activity: Mapped["Activity"] = relationship("Activity", back_populates="member_list")                   # what activity
    role: Mapped[str] = mapped_column(String(ROLE_LENGTH), default="")          # Person's role on the activity
    is_canceled: Mapped[bool] = mapped_column(default=False)                         
    registration: Mapped[str] = mapped_column(String(STATUS_LENGTH), default="")         # Person's registration status
    member_result: Mapped[str] = mapped_column(String(RESULT_LENGTH), default="")         # Person's activity result

    def __repr__(self) -> str:
        return f"ActivityMember(id={self.id!r}, person={self.person!r})"
    


class Activity(Base):
    '''An activity.'''
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)

    #
    # Trip information
    #
    date_start: Mapped[datetime.date] = mapped_column(Date)
    date_end: Mapped[datetime.date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(URL_LENGTH), default="")
    activity_url: Mapped[str] = mapped_column(String(URL_LENGTH), default="", index=True)
    committee: Mapped[str] = mapped_column(String(COMMITTEE_LENGTH), default="")
    branch: Mapped[str] = mapped_column(String(BRANCH_LENGTH), default="")
    activity_type: Mapped[str] = mapped_column(String(ACTIVITY_TYPE_LENGTH), default="")
    difficulty: Mapped[str] = mapped_column(String(DIFFICULTY_LENGTH), default="")
    leader_rating: Mapped[str] = mapped_column(String(LEADER_RATING_LENGTH), default="")
    milage: Mapped[str] = mapped_column(String(MILEAGE_LENGTH), default="")
    route_name: Mapped[str] = mapped_column(String(ROUTE_NAME_LENGTH), default="")
    route_link: Mapped[str] = mapped_column(String(URL_LENGTH), default="")
    status: Mapped[str] = mapped_column(String(STATUS_LENGTH), default="")
    result: Mapped[str] = mapped_column(String(RESULT_LENGTH), default="")

    #
    # Who went on the trip
    #
    member_list: Mapped[t.List[ActivityMember]] = relationship("ActivityMember", back_populates="activity",
                                                    cascade="all, delete, delete-orphan",
                                                    passive_deletes=True)
    
    #
    # Scraping information
    #
    scrapped_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    next_scrape: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    scrape_error: Mapped[str] = mapped_column(String(200), default="")
    scrape_error_count: Mapped[int] = mapped_column(default=0)
    scrape_error_time: Mapped[datetime.datetime | None] = mapped_column(DateTime)
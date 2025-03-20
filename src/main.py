import argparse
import traceback
import datetime
import re

from selenium import webdriver
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload


import econfig
import mtnschema
import mtndb
import mtnweb
import scrapester



def make_mtnweb(is_visible: bool = False) -> mtnweb.ScrapeMtnWeb:
    options = webdriver.FirefoxOptions()
    options.binary_location = econfig.get(econfig.FIREFOX_PATH)
    if not is_visible: 
        options.add_argument("-headless")
    driver = webdriver.Firefox(options=options)
    mtn_web = mtnweb.ScrapeMtnWeb(driver)
    return mtn_web

def make_mtndb(is_echo: bool = False) -> mtndb.MtnDB:
    engine = create_engine(econfig.get(econfig.DATABASE_URL), echo=is_echo)
    mtn_db = mtndb.MtnDB(engine)
    return mtn_db


YEAR_FIRST_DATE_PAT = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
DAY_FIRST_DASH_DATE_PAT = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
DAY_FIRST_SLASH_DATE_PAT = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
YEAR_FIRST_DATE = "%Y-%m-%d"
DAY_FIRST_DASH_DATE = "%m-%d-%Y"
DAY_FIRST_SLASH_DATE = "%m/%d/%Y"

def parse_date(date_str: str) -> datetime.date:
    M = YEAR_FIRST_DATE_PAT.match(date_str)
    if M:
        date = datetime.datetime.strptime(date_str, YEAR_FIRST_DATE).date()
        return date
    M = DAY_FIRST_DASH_DATE_PAT.match(date_str)
    if M:
        date = datetime.datetime.strptime(date_str, DAY_FIRST_DASH_DATE).date()
        return date
    M = DAY_FIRST_SLASH_DATE_PAT.match(date_str)
    if M:
        date = datetime.datetime.strptime(date_str, DAY_FIRST_SLASH_DATE).date()
        return date
    raise ValueError(f"Unrecognized date string: {date_str}")



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


def command_scrape(args):
    print(f"Running scrape with arguments: {args}")
    with make_mtnweb(is_visible=args.b) as mtn_web:
        with make_mtndb(is_echo=args.echosql) as mtn_db:
            scraper = scrapester.Scrapester(mtn_web, mtn_db, 
                                    econfig.get(econfig.MTN_WEB_USERNAME, override=args.user), 
                                    econfig.get(econfig.MTN_WEB_PASSWORD, override=args.password))
            scraper.is_scrape_future = args.fsf
            try:
                scraper.login()
                scraper.scrape_activity_for_profile(args.profile)
                print ("Done scraping")
            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()


                




def _select_person_by(mtn_session, profile_url: str, user_name: str) -> mtnschema.Person:
    """
    Selects a person from the database based on either profile_url or user_name.  
    profile_url takes precedence over user_name if both are provided.
    Args:
        mtn_session: The SQLAlchemy session to use for the query.
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
    result = mtn_session.execute(stmt).scalars().all()
    if len(result) != 1:
        raise ValueError(f"Expected 1 result, got {len(result)}")
    return result[0]




def command_whatdid(args):
    #print(f"Running whatdid with arguments: {args}")
    with make_mtndb(is_echo=args.echosql) as mtn_db:
        with mtn_db.session() as mtn_session:
            try:
                # Get the target person based a profile URL or the user name from command line or config file.
                target_person = _select_person_by(mtn_session, args.profile, econfig.get(econfig.MTN_WEB_USERNAME, override=args.user))
            except ValueError as e:
                print(f"Error: {e}")
                return
            
            print (f"{target_person.full_name} did:")
            target_person.activity_list.sort(key=lambda am: am.activity.date_start)
            for am in target_person.activity_list:
                a = am.activity
                if not args.type or args.type == a.activity_type:
                    print(f"  {a.date_start}: {a.name} ({a.activity_type})")



def command_diddo(args):
    print(f"Running diddo with arguments: {args}")
    trip_phrase = args.phrase.lower()
    with make_mtndb(is_echo=args.echosql) as mtn_db:
        with mtn_db.session() as mtn_session:
            try:
                target_person = _select_person_by(mtn_session, args.profile, econfig.get(econfig.MTN_WEB_USERNAME, override=args.user))
            except ValueError as e:
                print(f"Error: {e}")
                return
            
            print (f"{target_person.full_name} did do '{args.phrase}':")
            for am in target_person.activity_list:
                a = am.activity
                if trip_phrase in a.name.lower():
                    print(f"  {a.date_start}: {a.name} ({a.activity_type})")
    



def command_whowith(args):
    trip_date = parse_date(args.date)

    with make_mtndb(is_echo=args.echosql) as mtn_db:
        with mtn_db.session() as mtn_session:
            try:
                target_person = _select_person_by(mtn_session, args.profile, econfig.get(econfig.MTN_WEB_USERNAME, override=args.user))
            except ValueError as e:
                print(f"Error: {e}")
                return

                
            print (f"{target_person.full_name}")
            trip_list = trips_on_date(target_person, trip_date)
            for trip in trip_list:
                print (f"    {trip.date_start}: {trip.name} ({trip.activity_type})")
            person_list = people_on_trips(trip_list)
            if target_person.profile_url in person_list:
                del person_list[target_person.profile_url]
            sorted_person_list = sorted(person_list.values(), key=lambda u: u.full_name)

            for co_paddler in sorted_person_list:
                print (f"  {co_paddler.full_name}")
                is_on_trip = False
                for target_am in target_person.activity_list:
                    an_activity = target_am.activity
                    for a_member in an_activity.member_list:
                        if a_member.person == co_paddler:
                            print(f"    {an_activity.date_start}: {an_activity.name:<60} ({an_activity.activity_type})")
                            is_on_trip = True
                if not is_on_trip:
                    print ("  Not on trip")
                print ("")





def command_tripstatus(args):


    trip_date = parse_date(args.date)
    

    with make_mtndb(is_echo=args.echosql) as mtn_db:
        with mtn_db.session() as mtn_session:
            scraper: scrapester.Scrapester  | None = None
            mtn_web: mtnweb.ScrapeMtnWeb | None = None
            if args.update:
                mtn_web = make_mtnweb()
                scraper = scrapester.Scrapester(mtn_web, mtn_db,
                                econfig.get(econfig.MTN_WEB_USERNAME, override=args.user), 
                                econfig.get(econfig.MTN_WEB_PASSWORD, override=args.password),
                                session=mtn_session)
                scraper.login()
            try:


                try:
                    target_person = _select_person_by(mtn_session, args.profile, econfig.get(econfig.MTN_WEB_USERNAME, override=args.user))
                except ValueError as e:
                    print(f"Error: {e}")
                    return

                    
                print (f"{target_person.full_name}")
                trip_list = trips_on_date(target_person, trip_date)


                for an_activity in trip_list:
                    if args.update:
                        print (f"Updating {an_activity.name}")
                        scraper.activity_update(an_activity)
                    print (f"  {an_activity.date_start}-{an_activity.date_end} : {an_activity.name:<60} ({an_activity.activity_type})")
                    print (f"    {an_activity.activity_url}")
                    print (f"    {an_activity.branch} - {an_activity.committee}")
                    print (f"    {an_activity.difficulty}, leader: {an_activity.leader_rating}, milage: {an_activity.milage}")
                    print (f"    {an_activity.route_name}   ({an_activity.route_link})")
                    print (f"    {an_activity.status} - {an_activity.result}")
                    print (f"    last scrape: {an_activity.scrapped_at}, next scrape: {an_activity.next_scrape}")

                    for i, a_member in enumerate(an_activity.member_list):
                        u = a_member.person
                        print(f"      {i+1:2d} {u.full_name:40} {a_member.role}")

                    print ("")
            finally:
                if scraper:
                    scraper.close()
                    mtn_web.close()
                



def command_activity(args):
    print(f"Running bar with arguments: {args}")
    print(f"Activity: {args.actname}")
    activity_type = args.actname
    user_name = econfig.get(econfig.MTN_WEB_USERNAME, override=args.user)
    with make_mtndb(is_echo=args.echosql) as mtn_db:
        with mtn_db.session() as mtn_session:
            # stmt = session.query(mtnschema.Person).options(joinedload(mtnschema.Person.activity_list).joinedload(mtnschema.ActivityMember.activity)).filter(
            #         mtnschema.Person.user_name == "tkunger",
            #         mtnschema.Activity.activity_type == activity_type).order_by(mtnschema.Activity.date_start.desc())'

            stmt = select(mtnschema.Person).join(mtnschema.ActivityMember).join(mtnschema.Activity).filter(
                mtnschema.Person.user_name == user_name,
                mtnschema.Activity.activity_type == activity_type
            ).order_by(mtnschema.Activity.date_start.desc())


            # stmt = select(mtnschema.Activity).join(mtnschema.ActivityMember).join(mtnschema.Person).filter(
            #         # mtnschema.Person.user_name == user_name,
            #         mtnschema.Activity.activity_type == activity_type
            #     ).order_by(mtnschema.Activity.date_start.desc())

            result = mtn_session.execute(stmt).scalars().all()
            print (f"Found {len(result)} activities")


  

        for u in result:

            print (f"{u.full_name}")
            for am in u.activity_list:
                a = am.activity
                print(f"  {a.date_start}: {a.activity_type}  {a.name}")
                if a.activity_type != activity_type:
                    print ("NOT activity type")
                for am in a.member_list:
                    u = am.person
                    print(f"    {u.full_name:40} {am.role}")

            pass



def common_add(parser):
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-C', type=str, help='Path to configuration file')
    parser.add_argument('-S', '--echosql', action='store_true', help='enable SQL echo')
    parser.add_argument('-u', '--user', type=str, help='Username for mountaineers.org', required=False)
    parser.add_argument('-p', '--password', type=str, help='Password for mountaineers.org', required=False)

def common_process(args):
    if args.verbose:
        print("Verbose mode enabled")
    econfig.load_env(args.C)


def main():
    parser = argparse.ArgumentParser(description='Mountaineers command line tool')
    common_add(parser)

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Scrape command
    parser_scrape = subparsers.add_parser('scrape', help="Scrape a user's activity")
    parser_scrape.add_argument('--profile', type=str, help='user profile to scrape')
    parser_scrape.add_argument('-b', action='store_true', help='make browser visible')
    parser_scrape.add_argument('--fsf', action='store_true', help='Force scrape of future activities')
    parser_scrape.set_defaults(func=command_scrape)

    # whowith command command
    parser_whowith = subparsers.add_parser('whowith', help='''Who did I paddle with?  
                            The target user is identified by profile URL (--profile), command line user name (-u), or config file user name.''')
    parser_whowith.add_argument('--profile', type=str, help='Identify the target user by profile URL')
    parser_whowith.add_argument('date', type=str, help='Date of trip (YYYY-MM-DD)')
    parser_whowith.set_defaults(func=command_whowith)

    # whatdid command command
    parser_whatdid = subparsers.add_parser('whatdid', help='did a person do a trip?')
    parser_whatdid.add_argument('--profile', type=str, help='user profile to scrape')
    parser_whatdid.add_argument('--type', type=str, help='activity type', default="")
    parser_whatdid.set_defaults(func=command_whatdid)

    # diddo command command
    parser_diddo = subparsers.add_parser('diddo', help='did a person do a trip?')
    parser_diddo.add_argument('phrase', type=str, help='Date of trip (YYYY-MM-DD)')
    parser_diddo.add_argument('--profile', type=str, help='user profile to scrape')
    parser_diddo.set_defaults(func=command_diddo)

    # trip status command command
    parser_tripstatus = subparsers.add_parser('tripstatus', help='''Full status of a trip  
                            The target user is identified by profile URL (--profile), command line user name (-u), or config file user name.''')
    parser_tripstatus.add_argument('--profile', type=str, help='Identify the target user by profile URL')
    parser_tripstatus.add_argument('--update', action='store_true', default=False, help='Update the trips first.')
    parser_tripstatus.add_argument('date', type=str, help='Date of trip (YYYY-MM-DD)')
    parser_tripstatus.set_defaults(func=command_tripstatus)


    # activity command command
    parser_activity = subparsers.add_parser('activity', help='what trips of this activity type?')
    parser_activity.add_argument('actname', type=str, help='activity name')
    parser_activity.set_defaults(func=command_activity)



    args = parser.parse_args()
    common_process(args)
    if args.command:
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
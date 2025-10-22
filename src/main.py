import typing as t

import typer
from rich import print
from rich.table import Table
from rich.padding import Padding
from rich import box



import econfig
import util

econfig.load_env()



TABLE_BOX_STYE = box.SIMPLE_HEAD

app = typer.Typer(rich_markup_mode="rich")

@app.command()
def whowith(
    date_str: t.Annotated[str, typer.Argument(help="The trip date")],
    user: t.Annotated[str, typer.Option("-u", envvar=econfig.MTN_WEB_USERNAME, help="Target person's user name")] = None,
    profile: t.Annotated[str, typer.Option(help="Target person's profile")] = None,
):
    """
    When did I paddle with the people on this trip?

    The trip is identified by [bold yellow]date_str[/bold yellow].  All trips happening on that date will be
    reported on.  

    Your identify is determined by the user (-u) name or the --profile. 
    """
    if profile is None and user is None:
        print ("Error: You must specify a user name or a profile URL")
        return

    trip_date = util.parse_date(date_str)
    
    # Neo4j implementation
    with util.make_neo4j_db() as neo_db:
        # Find target person
        if profile:
            target_person = neo_db.person_find_by_url(profile)
        else:
            target_person = neo_db.person_find_by_username(econfig.get(econfig.MTN_WEB_USERNAME, override=user))
        
        if not target_person:
            print("Error: Person not found")
            return

        print(f"{target_person.full_name}")
        
        # Get activities on the specified date
        trip_list = neo_db.get_activities_on_date(target_person, trip_date)
        for trip in trip_list:
            print(f"    {trip.date_start}: {trip.name} ({trip.activity_type})")
        
        # Get all people who participated in these activities
        person_list = neo_db.get_people_on_activities(trip_list)
        if target_person.profile_url in person_list:
            del person_list[target_person.profile_url]
        sorted_person_list = sorted(person_list.values(), key=lambda u: u.full_name)

        for co_paddler in sorted_person_list:
            print(f"  {co_paddler.full_name}")
            co_table = Table("start", "Activity", "Type", box=TABLE_BOX_STYE)
            
            # Get shared activities between target person and co-paddler
            shared_activities = neo_db.get_shared_activities(target_person, co_paddler)
            for activity in shared_activities:
                co_table.add_row(str(activity.date_start), activity.name, activity.activity_type)
            
            if co_table.row_count > 0:
                print(Padding.indent(co_table, 4))
            else:
                print("    No shared activities found")
            print("")





@app.command()
def diddo(
    trip_phrase: t.Annotated[str, typer.Argument(help="The phrase to search for")],
    user: t.Annotated[str, typer.Option("-u", envvar=econfig.MTN_WEB_USERNAME, help="Login user name")] = None,
    profile: t.Annotated[str, typer.Option(help="Target person's profile")] = None,
):
    trip_phrase_lower = trip_phrase.lower()
    
    # Neo4j implementation
    with util.make_neo4j_db() as neo_db:
        # Find target person
        if profile:
            target_person = neo_db.person_find_by_url(profile)
        else:
            target_person = neo_db.person_find_by_username(user)
        
        if not target_person:
            print("Error: Person not found")
            return
        
        print(f"{target_person.full_name} did do '{trip_phrase}':")
        
        # Get all activities for the person
        activities_with_participation = neo_db.get_person_activities(target_person)
        for activity, participation in activities_with_participation:
            if trip_phrase_lower in activity.name.lower():
                print(f"  {activity.date_start}: {activity.name} ({activity.activity_type})")


@app.command()
def tripstatus(
    trip_date_str: t.Annotated[str, typer.Argument(help="The trip date")],
    update: t.Annotated[bool, typer.Option(help="Update the trip")] = False,
    user: t.Annotated[str, typer.Option("-u", envvar=econfig.MTN_WEB_USERNAME, help="Login user name")] = None,
    password: t.Annotated[str, typer.Option("-p", envvar=econfig.MTN_WEB_PASSWORD, help="Login password")] = None,
    profile: t.Annotated[str, typer.Option(help="Target person's profile")] = None,
):
    """
    Show status and details of trips on a specific date.
    
    The trip is identified by [bold yellow]trip_date_str[/bold yellow]. All trips happening on that date will be
    reported on with detailed information including participants, routes, and status.
    
    Your identity is determined by the user (-u) name or the --profile.
    """
    trip_date = util.parse_date(trip_date_str)

    # Neo4j implementation
    with util.make_neo4j_db() as neo_db:
        scraper = None
        mtn_web = None
        if update:
            mtn_web = util.make_mtnweb()
            import neo4j_scrapester
            scraper = neo4j_scrapester.Neo4jScrapester(mtn_web, neo_db, user, password)
            scraper.login()
        
        try:
            # Find target person
            if profile:
                target_person = neo_db.person_find_by_url(profile)
            else:
                target_person = neo_db.person_find_by_username(user)
            
            if not target_person:
                print("Error: Person not found")
                return

            print(f"{target_person.full_name}")
            trip_list = neo_db.get_activities_on_date(target_person, trip_date)

            for an_activity in trip_list:
                if update and scraper:
                    print(f"Updating {an_activity.name}")
                    scraper.activity_update(an_activity)
                
                print(f"  {an_activity.date_start}-{an_activity.date_end} : {an_activity.name:<60} ({an_activity.activity_type})")
                print(f"    {an_activity.activity_url}")
                print(f"    {an_activity.branch} - {an_activity.committee}")
                print(f"    {an_activity.difficulty}, leader: {an_activity.leader_rating}, milage: {an_activity.milage}")
                print(f"    {an_activity.route_name}   ({an_activity.route_link})")
                print(f"    {an_activity.status} - {an_activity.result}")
                print(f"    last scrape: {an_activity.scrapped_at}, next scrape: {an_activity.next_scrape}")

                member_table = Table("count", "name", "role", box=TABLE_BOX_STYE)
                participants = neo_db.get_activity_participants(an_activity)
                for i, (participant, participation) in enumerate(participants):
                    member_table.add_row(str(i+1), participant.full_name, participation.role)
                print(Padding.indent(member_table, 4))

                print("")
        finally:
            if scraper:
                scraper.close()
            if mtn_web:
                mtn_web.close()


@app.command()
def scrape(
    browser: t.Annotated[bool, typer.Option("-b", help="Show browser window")] = False,
    fsf: t.Annotated[bool, typer.Option(help="Force scrape all future activities")] = False,
    user: t.Annotated[str, typer.Option("-u", envvar=econfig.MTN_WEB_USERNAME, help="Login user name")] = None,
    password: t.Annotated[str, typer.Option("-p", envvar=econfig.MTN_WEB_PASSWORD, help="Login password")] = None,
    profile: t.Annotated[str, typer.Option(help="Target person's profile")] = None,
):
    print("scrape")
    
    # Neo4j implementation
    with util.make_mtnweb(is_visible=browser) as mtn_web:
        with util.make_neo4j_db() as neo_db:
            import neo4j_scrapester
            scraper = neo4j_scrapester.Neo4jScrapester(mtn_web, neo_db, user, password)
            scraper.is_scrape_future = fsf

            scraper.login()
            scraper.scrape_person_activity(profile_url=profile)
            print("Done scraping")



if __name__ == "__main__":
    app()
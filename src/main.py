import typing as t
import datetime

import typer
from rich import print
from rich.table import Table
from rich.padding import Padding
from rich import box

import econfig
import util
import mtn_logic

econfig.load_env()



TABLE_BOX_STYE = box.SIMPLE_HEAD

app = typer.Typer(rich_markup_mode="rich")

@app.command()
def whowith(
    person: t.Annotated[str, typer.Argument(help="Target person's name, profile url, or user name")],
    date_str: t.Annotated[str, typer.Argument(help="The trip date")]
):
    """
    When did I paddle with the people on this trip?


    The trip is identified by [bold yellow]date_str[/bold yellow].  All trips happening on that date will be
    reported on.

    """


    trip_date = util.parse_date(date_str)
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)

        try:
            awi = logic.who_with(person, trip_date)
        except mtn_logic.MtnException as e:
            print(f"Error: {e}")
            return
        
        
        print(f"{awi.target_person.full_name}")
        
        for activity in awi.target_activities:
            print(f"    {activity.date_start}: {activity.name} ({activity.activity_type})")
        

        sorted_person_list = sorted(awi.shared, key=lambda u: u.shared_person.full_name)

        for co_paddler in sorted_person_list:
            print(f"  {co_paddler.shared_person.full_name}")
            co_table = Table("Start", "Activity", "Type", box=TABLE_BOX_STYE)
            
            # Get shared activities between target person and co-paddler
            for activity in co_paddler.activites:
                co_table.add_row(str(activity.date_start), activity.name, activity.activity_type)
            
            if co_table.row_count > 0:
                print(Padding.indent(co_table, 4))
            else:
                print("    No shared activities found")
            print("")





@app.command()
def diddo(
        person: t.Annotated[str, typer.Argument(help="Target person's profile url, name, or username")],
        trip_phrase: t.Annotated[str, typer.Argument(help="The phrase to search for in activity titles")],
    ):
    """Search for activities containing a phrase."""
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)

        try:
            matching_activities = logic.did_do(person, trip_phrase)
        except mtn_logic.MtnException as e:
            print(f"Error: {e}")
            return
    
        print(f"{person} did do '{trip_phrase}':")
        for activity in matching_activities:
            print(f"  {activity.date_start}: {activity.name} ({activity.activity_type})")


@app.command()
def didwhen(
        person: t.Annotated[str, typer.Argument(help="Target person's profile url, name, or username")],
        date_str: t.Annotated[str, typer.Argument(help="The activity date")],
    ):
    """Search for activities on a specific date."""
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)

        try:
            activity_date = util.parse_date(date_str)
            matching_activities = logic.did_when(person, activity_date)
        except mtn_logic.MtnException as e:
            print(f"Error: {e}")
            return
        
        print(f"{person} did on {date_str}:")
        for activity in matching_activities:
            print(f"  {activity.date_start}: {activity.name} ({activity.activity_type})")



@app.command()
def tripstatus(
        person: t.Annotated[str, typer.Argument(help="Target person's profile url, name, or username")],
        trip_date_str: t.Annotated[str, typer.Argument(help="The trip date")],
        update: t.Annotated[bool, typer.Option(help="Update the trip")] = False,
        user: t.Annotated[str, typer.Option("-u", envvar=econfig.MTN_WEB_USERNAME, help="Login user name")] = None,
        password: t.Annotated[str, typer.Option("-p", envvar=econfig.MTN_WEB_PASSWORD, help="Login password")] = None,
        browser: t.Annotated[bool, typer.Option("-b", help="Show browser window")] = False,
    ):
    """
    Show status and details of trips on a specific date.
    
    The trip is identified by [bold yellow]trip_date_str[/bold yellow]. All trips happening on that date will be
    reported on with detailed information including participants, routes, and status.
    
    Your identity is determined by the user (-u) name or the --profile.
    """
    trip_date = util.parse_date(trip_date_str)


    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        target_person, activity_list = logic.trip_status(
                user,
                password,
                person,
                trip_date,
                browser,
                update,
                progress_callback=print
        )
        

        print(f"{target_person.full_name}")

        for activity_info in activity_list:
            
            print(f"  {activity_info.date_start}-{activity_info.date_end} : {activity_info.name:<60} ({activity_info.activity_type})")
            print(f"    {activity_info.activity_url}")
            print(f"    {activity_info.branch} - {activity_info.committee}")
            print(f"    {activity_info.difficulty}, leader: {activity_info.leader_rating}, milage: {activity_info.milage}")
            print(f"    {activity_info.route_name}   ({activity_info.route_link})")
            print(f"    {activity_info.status} - {activity_info.result}")
            print(f"    last scrape: {activity_info.scrapped_at}, next scrape: {activity_info.next_scrape}")

            # TODO: return fully populated activity participation and participants. 
            # member_table = Table("count", "name", "role", box=TABLE_BOX_STYE)
            # for i, participation in enumerate(participants):
            #     member_table.add_row(str(i+1), participation.person.full_name, participation.role)
            # print(Padding.indent(member_table, 4))

            print("")


@app.command()
def scrape(
    person: t.Annotated[str, typer.Argument(help="Target person's profile url, name, or username")],
    browser: t.Annotated[bool, typer.Option("-b", help="Show browser window")] = False,
    fsf: t.Annotated[bool, typer.Option(help="Force scrape all future activities")] = False,
    user: t.Annotated[str, typer.Option("-u", envvar=econfig.MTN_WEB_USERNAME, help="Login user name")] = None,
    password: t.Annotated[str, typer.Option("-p", envvar=econfig.MTN_WEB_PASSWORD, help="Login password")] = None,
):
    """Scrape activity data from the mountaineers website."""
    print("scrape")
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        
        try:
            result = logic.scrape_person_activities(
                username=user,
                password=password,
                name_url_user=person,
                is_visible_browser=browser,
                force_scrape_future=fsf,
                progress_callback=print
            )
        except mtn_logic.MtnException as e:
            print(f"Error during scraping: {e}")
            return
        
        if result["status"] == "completed":
            print("Done scraping")
        elif result["status"] == "error":
            print(f"Error during scraping: {', '.join(result['errors'])}")


@app.command()
def scrapedue(
    days_past: t.Annotated[int, typer.Option("-d", help="Number of days since person was last scraped")] = 4,
    browser: t.Annotated[bool, typer.Option("-b", help="Show browser window")] = False,
    fsf: t.Annotated[bool, typer.Option(help="Force scrape all future activities")] = False,
):
    """Show activities that are due for scraping within the next N days."""
    scrape_cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_past)
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        
        people_list = logic.persons_due_scrape(scrape_cutoff_date)

        for person in people_list:
            print(f"{person.full_name} (last scraped: {person.last_scrapped})")
            try:
                result = logic.scrape_person_activities(
                    username=econfig.get(econfig.MTN_WEB_USERNAME),
                    password=econfig.get(econfig.MTN_WEB_PASSWORD),
                    name_url_user=person.profile_url,
                    is_visible_browser=browser,
                    force_scrape_future=fsf,
                    progress_callback=lambda s: print (f"{person.full_name}: {s}")
                )
            except mtn_logic.MtnException as e:
                print(f"Error during scraping: {e}")
                return
            
            if result["status"] == "completed":
                print("Done scraping")
            elif result["status"] == "error":
                print(f"Error during scraping: {', '.join(result['errors'])}")
                


@app.command()
def history(
    person: t.Annotated[str, typer.Argument(help="Target person's profile url, name, or username")],
):
    """Show activity history for a person."""
    print("history")
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        
        try:
            activity_part_list = logic.get_person_activity_history(person)
        except mtn_logic.MtnException as e:
            print(f"Error: {e}")
            return
        
        print(f"Activity history for {person}:")
        history_table = Table("#", "Date", "Activity", "Type", "Role", box=TABLE_BOX_STYE)
        history_table.columns[0].justify = "right"
        history_table.columns[2].max_width = 65
        history_table.columns[2].overflow = "ignore"
        history_table.columns[3].max_width = 30
        history_table.columns[3].overflow = "ignore"
        i = 1
        for activity, participation in activity_part_list:
            history_table.add_row(str(i), str(activity.date_start), activity.name, activity.activity_type, participation.role)
            i += 1
        print(Padding.indent(history_table, 4))


if __name__ == "__main__":
    app()
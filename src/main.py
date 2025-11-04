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
def whowho(
    person1: t.Annotated[str, typer.Argument(help="First person's name, profile url, or user name")],
    person2: t.Annotated[str, typer.Argument(help="Second person's name, profile url, or user name")]
):
    """
    Find what activities two people did together.

    Shows all activities that both [bold yellow]person1[/bold yellow] and [bold yellow]person2[/bold yellow] 
    participated in, along with whether each person's activities have been scraped.
    """
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)

        try:
            result = logic.who_who(person1, person2)
        except mtn_logic.MtnException as e:
            print(f"Error: {e}")
            return
        
        # Display both people with their scrape status
        print(f"\n[bold]{result.person1.full_name}[/bold]")
        print(f"  Activities scraped: {'Y' if result.person1.act_is_scrapped else 'n'}")
        if result.person1.act_last_scrapped:
            print(f"  Last scraped: {result.person1.act_last_scrapped.strftime('%Y-%m-%d %H:%M')}")
        
        print(f"\n[bold]{result.person2.full_name}[/bold]")
        print(f"  Activities scraped: {'Y' if result.person2.act_is_scrapped else 'n'}")
        if result.person2.act_last_scrapped:
            print(f"  Last scraped: {result.person2.act_last_scrapped.strftime('%Y-%m-%d %H:%M')}")
        
        # Display shared activities
        print(f"\n[bold]Shared Activities ({len(result.shared_activities)}):[/bold]")
        
        if result.shared_activities:
            activity_table = Table("Date", "Activity", "Type", box=TABLE_BOX_STYE)
            
            for activity in result.shared_activities:
                activity_table.add_row(
                    str(activity.date_start), 
                    activity.name, 
                    activity.activity_type
                )
            
            print(Padding.indent(activity_table, 2))
        else:
            print("  No shared activities found")
        
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
    days_past: t.Annotated[float, typer.Option("-d", "--days", help="Number of days since person was last scraped.  A float, may include fractional days: 3.5")] = 4,
    browser: t.Annotated[bool, typer.Option("-b", help="Show browser window")] = False,
    fsf: t.Annotated[bool, typer.Option(help="Force scrape all future activities")] = False,
    limit: t.Annotated[int, typer.Option("-l", "--limit", help="Limit the number scraped")] = 0,
    proportional: t.Annotated[bool, typer.Option("-p", "--proportional", help="Limit the scrape to a proportional number based on days_past.  If you want to scrape everyone every N days, assuming one run per day, ceil(1/N) people's activiteis are scrapped.")] = False,
):
    """Scrape the activity profile of people who are due to have their activities updated.  
    There are a couple stratigies for choosing which people's activities get updated.  
    
    By Date
      -d N : set the number of days past.  Everyone who's last scrape is before that time will be updated.

    Proportional
      -d N -p: Set the number of past days but limit the number of people updated to 1/N.  
                This assumes one run per day and will have the effect of updating 1/N of the people 
                every run and all people will get updated every N days.

    Limit
      -d N -l L : Limit the number of people updated.  Assuming one run per day, everyone will 
                get updated every L days.  If N < L then N has little effect.  If N > L then'
                it controls how often profiles are updated.
    """
    scrape_cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_past)
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        
        people_list = logic.persons_act_due_scrape(scrape_cutoff_date, limit=limit, proportional=proportional)

        for person in people_list:
            print(f"{person.full_name} (last scraped: {person.act_last_scrapped})")
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


@app.command()
def lsscrape(
    sort: t.Annotated[str, typer.Option(help="Sort order: 'name' (default) or 'date'")] = "name"
):
    """
    List all people who have had their activities scraped.
    
    Shows people with [bold yellow]act_is_scrapped=True[/bold yellow], displaying their name,
    activity scrape timestamp, profile scrape timestamp, and profile URL.
    """
    
    if sort not in ["name", "date"]:
        print(f"Error: Invalid sort option '{sort}'. Use 'name' or 'date'.")
        return
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        
        try:
            people = logic.list_scraped_people(sort_by=sort)
        except Exception as e:
            print(f"Error: {e}")
            return
        
        if not people:
            print("No people with scraped activities found.")
            return
        
        # Display table
        print(f"\n[bold]People with Scraped Activities ({len(people)}):[/bold]")
        
        scrape_table = Table(
            "Name", 
            "Activity Scraped", 
            "Profile Scraped", 
            "Profile URL",
            box=TABLE_BOX_STYE
        )
        scrape_table.columns[0].max_width = 30
        scrape_table.columns[3].max_width = 80
        scrape_table.columns[3].overflow = "ignore"

        
        for person in people:
            act_scrape_str = person.act_last_scrapped.strftime('%Y-%m-%d %H:%M') if person.act_last_scrapped else "Never"
            prof_scrape_str = person.prof_last_scrapped.strftime('%Y-%m-%d %H:%M') if person.prof_last_scrapped else "Never"
            
            scrape_table.add_row(
                person.full_name,
                act_scrape_str,
                prof_scrape_str,
                person.profile_url
            )
        
        print(Padding.indent(scrape_table, 2))
        print("")


@app.command()
def rmscrape(
    people: t.Annotated[list[str], typer.Argument(help="One or more people (name, profile url, or username)")]
):
    """
    Remove people from activity scraping by setting act_is_scrapped to False.
    
    Takes one or more person identifiers. For each person, sets [bold yellow]act_is_scrapped=False[/bold yellow]
    while leaving [bold yellow]act_last_scrapped[/bold yellow] unchanged. If a person is not found, 
    the command continues to the next person.
    """
    
    # Use business logic layer
    with util.make_neo4j_db() as neo_db:
        logic = mtn_logic.MountaineerLogic(neo_db)
        
        for person_identifier in people:
            try:
                updated_person = logic.remove_person_from_scrape(person_identifier)
                print(f"✓ {updated_person.full_name}: Removed from activity scraping (act_is_scrapped=False)")
            except mtn_logic.MtnException:
                print(f"✗ {person_identifier}: Person not found")


if __name__ == "__main__":
    app()

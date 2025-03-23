import typing as t
import datetime
import dataclasses
import re


from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementNotInteractableException, WebDriverException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
import time
from selenium.webdriver.common.action_chains import ActionChains

import econfig


PROFILE_PAGE_PROFILE = "Profile"
PROFILE_PAGE_ACTIVITIES = "My Activities"

MEMBER_STATUS_REGISTERED = "Registered"
MEMBER_STATUS_WAITLISTED = "Waitlisted"
MEMBER_STATUS_CANCELED = "Canceled"

MEMBER_RESULT_SUCCESS = "Successful"
MEMBER_RESULT_CANCELED = "Canceled"


ACTIVITY_STATUS_FUTURE = "FU"
ACTIVITY_STATUS_PAST = "PA"
ACTIVITY_STATUS_CLOSED = "CL"

ACTIVITY_RESULT_CANCELED = "Canceled"
ACTIVITY_RESULT_SUCCESS = "Success"
ACTIVITY_RESULT_TURNED_AROUND = "Turned Around"

# Strings that identify errors.  May differ by browser.
ERROR_STRING_DNS = "e=dnsNotFound"

# Suggested delay for known errors.
DELAY_DNS_ERROR = 1 * 60
DELAY_TIMEOUT = 30





class ScrapeException(Exception):
    def __init__(self, page_link: str, message: str):
        super().__init__()
        self.page_link = page_link
        self.message = message


class WebResponseException(ScrapeException):
    '''An error doing something on the website which should work.  This could succeed if retried.'''
    def __init__(self, page_link: str, message: str, delay_seconds: int = 0):
        super().__init__(page_link, message)
        self.delay_seconds = delay_seconds
        
class PageFormatException(ScrapeException):
    def __init__(self, page_link: str, message: str):
        super().__init__(page_link, message)


class MissingContentException(ScrapeException):
    def __init__(self, page_link: str, message: str):
        super().__init__(page_link, message)
        


@dataclasses.dataclass
class ScrapedUser():
    user_name: str = ""
    password: str = ""
    full_name: str = ""
    profile_url: str = ""
    portrait_url: str = ""
    email: str = ""
    branch: str = ""


@dataclasses.dataclass
class ScrapedActivityMember():
    activity_url: str = ""
    activity_name: str = ""
    member_name: str = ""
    member_url: str = ""
    is_future: bool = False
    is_canceled: bool = False
    role: str = ""
    registration: str = ""
    member_result: str = ""
    activity_result: str = ""

   
@dataclasses.dataclass
class ScrapedActivity():
    date_start: datetime.date | None = None
    date_end: datetime.date | None = None
    name: str = ""
    url: str = ""
    committee: str = ""
    branch: str = ""
    activity_type: str = ""
    difficulty: str = ""
    leader_rating: str = ""
    milage: str = ""
    route_name: str = ""
    route_url: str = ""
    status: str = ""
    result: str = ""
    participants: list[ScrapedActivityMember] = dataclasses.field(default_factory=list)


ROLE_PAT = re.compile(r"^Role: (.*)$")
STATUS_PAT = re.compile(r"^Status: (.*)$")

class ScrapeMtnWeb():

    _SINGLE_DATE_PAT = re.compile(r"^\w{3}, (\w{3} \d{1,2}, \d{4})$")
    _DATE_TIME_PAT = re.compile(r"^\w{3}, (\w{3} \d{1,2}, \d{4}) from.*$")
    _DATE_RANGE_PAT = re.compile(r"^\w{3}, (\w{3} \d{1,2}, \d{4}) . \w{3}, (\w{3} \d{1,2}, \d{4})$")
    _DATE_FORMAT = "%b %d, %Y"


    def __init__(self, driver):
        self._driver = driver
        self._is_logged_in = False
        self.MTN_WEB_URL = econfig.get("MTN_WEB_URL")
        self.MTN_WEB_LOGIN = f"{self.MTN_WEB_URL}login"
        self.MTN_WEB_PROFILE = f"{self.MTN_WEB_URL}members/"
        self.MTN_WEB_PAGE_ACTIVITIES = "/member-activities"


    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self):
        self._driver.quit()


    def wait_for_element1(self, parent, by, selector, timeout) -> bool:
        def test_item(parent, by, selector):
            try:
                el = parent.find_element(by, selector)
                if el.is_displayed():
                    return True
            except Exception:
                pass
            return False
        
        wait = WebDriverWait(self._driver, timeout=timeout)
        try:
            wait.until(lambda x : test_item(parent, by, selector))
        except Exception:
            return False
        return True
 

    def parse_date(self, date_str: str) -> t.Tuple[datetime.date, datetime.date]:
        M = self._SINGLE_DATE_PAT.match(date_str)
        if M:
            date = datetime.datetime.strptime(M.group(1), self._DATE_FORMAT).date()
            return date, date
        M = self._DATE_TIME_PAT.match(date_str)
        if M:
            date = datetime.datetime.strptime(M.group(1), self._DATE_FORMAT).date()
            return date, date
        M = self._DATE_RANGE_PAT.match(date_str)
        if M:
            start_date = datetime.datetime.strptime(M.group(1), self._DATE_FORMAT).date()
            end_date = datetime.datetime.strptime(M.group(2), self._DATE_FORMAT).date()
            return start_date, end_date
        raise ValueError(f"Unrecognized date string: {date_str}")
    

    def login(self, username: str, password: str):
        # TODO: check if already logged in
        self._driver.get(self.MTN_WEB_LOGIN)
        time.sleep(2)  # Wait for the page to load

        # Fill in login credentials
        try:
            username_field = self._driver.find_element("id", "__ac_name")
        except Exception:
            raise PageFormatException(self._driver.current_url, "username field")
        try:    
            password_field = self._driver.find_element("id", "__ac_password")
        except Exception:
            raise PageFormatException(self._driver.current_url, "password: field")

        username_field.send_keys(username)
        password_field.send_keys(password)

        # Submit the login form
        try:
            login_button = self._driver.find_element("id", "buttons-login")
        except Exception:
            raise PageFormatException(self._driver.current_url, "login button")
        login_button.click()
        time.sleep(2)  # Wait for the next page to load

        # TODO: Check if login was successful

        self._is_logged_in = True



    def navigate_current_user_profile(self) -> ScrapedUser:

        #
        # Navigate to my profile page and scrape some information.
        #
        try:
            profile_element = self._driver.find_element(By.XPATH, "//li[@class='user menu hide-on-mobile']")
        except Exception:
            raise PageFormatException(self._driver.current_url, "user find profile icon in top bar")
        try:
            hover_element = ActionChains(self._driver).move_to_element(profile_element)
            hover_element.perform()
        except Exception as e:
            raise WebResponseException(self._driver.current_url, "user move to profile icon in top bar") from e


        try:
            specific_link = self._driver.find_element(By.PARTIAL_LINK_TEXT, "My Profile")
            specific_link.click()  # Click the link if needed 
        except Exception as e:
            raise WebResponseException(self._driver.current_url, "user click on My Profile") from e

        time.sleep(2)

        return self._scrape_profile()
    


    def navigate_to_profile(self, profile_link: str) -> ScrapedUser:
        '''Navigate to a user's profile page and scrape some information.
        Parameters:
            profile_link:  The URL of the user's profile page.
                            This may be the full profile or just the last component, 
                            which is usually the person's name ('tom-unger/')
        Returns:
            A ScrapedUser object with the profile information.
        '''

        if not profile_link.startswith("http"):
            profile_link = self.MTN_WEB_PROFILE + profile_link

        try:
            self._driver.get(profile_link)
        except WebDriverException as e:
            if ERROR_STRING_DNS in e.msg:
                # A recognized error.  Delay for 5 minutes
                raise WebResponseException(profile_link, "DNS not found", DELAY_DNS_ERROR) from e
            # Not a recognized error, raise it.
            raise
        return self._scrape_profile()
    

    
    def _scrape_profile(self) -> ScrapedUser:
        '''Scrape the profile page for the current user.  Assume that the browser
        is on the user's profile page.  
        
        Returns:
            ScrapedUser object with the profile information.
        '''

        user = ScrapedUser()
        user.profile_url = self._driver.current_url
        try:
            profile_el = self._driver.find_element(By.XPATH, "//div[@class='profile-wrapper']")
        except Exception:
            raise PageFormatException(self._driver.current_url, "user profile wrapper")
        try:
            # /html/body/div[2]/div/div[2]/article/div/article/div[1]/div/div[1]/img
            portrait_img_el = profile_el.find_element(By.XPATH, "//div[@class='portrait']/img")
            user.portrait_url = portrait_img_el.get_attribute('src')
        except Exception:
            raise PageFormatException(self._driver.current_url, "user portrait")
        try:
            user.full_name = profile_el.find_element(By.TAG_NAME,"h1").text.title()
        except Exception:
            raise PageFormatException(self._driver.current_url, "user full name")
        try:
            #
            # Details item contains one or more details including: Profile, Branch, Member since,
            #
            ul_el = profile_el.find_element(By.XPATH, "//ul[@class='details no-bullets']")
            for li_el in ul_el.find_elements(By.TAG_NAME, "li"):
                if "Branch" in li_el.text:
                    user.branch = li_el.find_element(By.TAG_NAME, "a").text
        except Exception:
            raise PageFormatException(self._driver.current_url, "user branch")
        try:
            email_a_el = profile_el.find_element(By.XPATH,"//div[@class='email']/a")
            user.email = email_a_el.text
        except Exception:
            raise PageFormatException(self._driver.current_url, "user email")
       
        return  user



    def scrape_member_activities(self, profile_link: str) -> list[ScrapedActivityMember]:
        activities_link = profile_link + self.MTN_WEB_PAGE_ACTIVITIES
        try:
            self._driver.get(activities_link)
        except WebDriverException as e:
            if ERROR_STRING_DNS in e.msg:
                # A recognized error.  Delay for 5 minutes
                raise WebResponseException(activities_link, "DNS not found", DELAY_DNS_ERROR) from e
            # Not a recognized error, raise it.
            raise
        
        #
        # Wait for history to load
        #
        # //*[@id="content"]/div/div/section/table/thead/tr/th[5]
        # #content > div > div > section > table > thead > tr > th:nth-child(5)
        if not self.wait_for_element1(self._driver, By.XPATH, "//section/table[@class='listing']/thead/tr/th[5]", 60):
            raise WebResponseException(self._driver.current_url, "trip history not loaded.")
        time.sleep(2)

        #
        # Enabled canceled trips
        #
        try:
            items = self._driver.find_elements(By.XPATH, "//div[@class='filter']")
        except Exception:
            raise PageFormatException(self._driver.current_url, "activity filter items for canceled")
        is_canceled_enabled = False
        for item in items:
            if item.text == 'Show canceled':
                try:
                    cb = item.find_element(By.XPATH, "//input[@type='checkbox']")
                    cb.click()
                    is_canceled_enabled = True
                    break
                except Exception:
                    pass
            if not is_canceled_enabled:
                raise PageFormatException(self._driver.current_url, "activity show canceled checkbox not found")

        #
        # Get a list of all trips
        #     
        trip_list = []
        try:
            web_trips = self._driver.find_elements(By.XPATH, "//tr[@class='activity-listing']")
        except Exception:  
            raise PageFormatException(self._driver.current_url, "activity list of trips [activity-listing]")
        for web_trip in web_trips:

            #
            # Start collecting trip data.  Future and past trips have some same and some different fields.
            #
            trip_member = ScrapedActivityMember()


            #
            # Table entry for Activity/Event has a link to the trip page.
            #
            try:
                ae_item = web_trip.find_element(By.CSS_SELECTOR, "td[data-th='Activity/Event']")
            except Exception:
                raise PageFormatException(self._driver.current_url, "activity table data for Activity/Event")
            try:
                ae_link = ae_item.find_element(By.TAG_NAME, "a")
            except Exception:
                raise PageFormatException(self._driver.current_url, "activity link for Activity/Event")
            trip_member.activity_url = ae_link.get_attribute("href")
            trip_member.activity_name = ae_link.text


            #
            # Now look for a field which will tell us if this item is future or past.
            #
            try:
                # /html/body/div[2]/div/div[2]/article/div/article/div/div/table/tbody/tr[1]/td[5]
                trip_member.registration = web_trip.find_element(By.CSS_SELECTOR, "td[data-th='Status']").text
                trip_member.is_future = True
            except Exception:
                pass

            if trip_member.is_future:
                # Get additional future trip fields.
                try:   
                    trip_member.role = web_trip.find_element(By.CSS_SELECTOR, "td[data-th='Role']").text
                except Exception:
                    raise PageFormatException(self._driver.current_url, "activity table data for Role")
                
            else:
                # Get additional past trip fields.
                # Role and personal result are in the same table cell.
                try:
                    rr = web_trip.find_element(By.CSS_SELECTOR, "td[data-th='Role: Result']")
                except Exception:
                    raise PageFormatException(self._driver.current_url, "activity table data for Role: Result")
                try:
                    rr_children = rr.find_elements(By.TAG_NAME, "span")
                except Exception:
                    raise PageFormatException(self._driver.current_url, "activity Role: Result children")
                trip_member.role = rr_children[0].text
                if len(rr_children) >= 3:
                    trip_member.member_result = rr_children[2].text
                try:
                    trip_member.registration = web_trip.find_element(By.CSS_SELECTOR, "td[data-th='Registration Status'").text
                except Exception:
                    raise PageFormatException(self._driver.current_url, "activity table data for Registration Status")
                try:
                    tr_el = web_trip.find_element(By.CSS_SELECTOR, "td[data-th='Trip Result'")
                    trip_member.activity_result = tr_el.text
                except Exception:
                    raise PageFormatException(self._driver.current_url, "activity table data for Trip Result")

            trip_member.is_canceled = trip_member.registration == MEMBER_STATUS_CANCELED or trip_member.activity_result == MEMBER_RESULT_CANCELED
            trip_list.append(trip_member)

        return trip_list
        


    def get_trip_details(self, trip_link: str) -> ScrapedActivity:
        try:
            self._driver.get(trip_link)
        except WebDriverException as e:
            if ERROR_STRING_DNS in e.msg:
                # A recognized error. 
                raise WebResponseException(trip_link, "DNS not found", DELAY_DNS_ERROR) from e
            # Not a recognized error, raise it.
            raise
        except TimeoutError as e:
            raise WebResponseException(trip_link, "Timeout", DELAY_TIMEOUT) from e
        time.sleep(2)

        trip = ScrapedActivity()
        trip.url = trip_link

        # Trip name is in a header element.
        try:
            trip.name = self._driver.find_element(By.XPATH, "//h1[@class='documentFirstHeading']").text
        except Exception:
            raise PageFormatException(trip_link, "trip name")
        
        if "this page does not seem to exist" in trip.name.lower():
            raise MissingContentException(trip_link, "Trip does not exist")
        
        # Trip details are in list items within "<div class="program-core">"
        #  which contains multiple lists:  <ul class="details">
        # So, find the <div> then all the <ul> within it.
        try:
            core_element = self._driver.find_element(By.XPATH, "//div[@class='program-core']")
        except Exception:
            raise PageFormatException(trip_link, "trip details div[program-core]")
        try:
            details_el_list = core_element.find_elements(By.XPATH, "//ul[@class='details']")
        except Exception:
            raise PageFormatException(trip_link, "trip details ul[details]")
        
        #
        # Now loop through each list and it's list items.
        # Test each for contents and extract.
        #
        trip_date_str = ""
        for details_list_el in details_el_list:
            
            try:
                detail_item_el = details_list_el.find_elements(By.TAG_NAME, "li")
            except Exception:
                raise PageFormatException(trip_link, "trip details list items")
            for detail_el in detail_item_el:
                label = ""
                try:
                    label_el = detail_el.find_element(By.TAG_NAME, "label")
                    label = label_el.text
                except Exception:
                    pass
                detail_el_text = detail_el.text

                if label == "" and not trip_date_str:
                    trip_date_str = detail_el.text
                elif label == "When:":
                    trip_date_str = detail_el_text.replace("When: ", "")
                elif label == "Committee:":
                    # Sometimes the name appears in a link
                    try:
                        trip.committee = detail_el.find_element(By.TAG_NAME, "a").text
                    except Exception:
                        pass
                    if not trip.committee:
                        # Other times, not in a link
                        trip.committee = detail_el_text.replace("Committee: ", "")
                elif label == "Difficulty:":
                    trip.difficulty = detail_el_text.replace("Difficulty: ", "")
                elif label == "Leader Rating:":
                    trip.leader_rating = detail_el_text.replace("Leader Rating: ", "")
                elif label == "Activity Type:":
                    trip.activity_type = detail_el_text.replace("Activity Type: ", "")
                elif label == "Branch:":
                    trip.branch = detail_el_text.replace("Branch: ", "")
                elif "Mileage:" in detail_el_text:
                    trip.milage = detail_el_text.replace("Mileage: ", "")

        # Test fields were found
        if not trip_date_str:
            raise PageFormatException(trip_link, "trip date")
        
        #
        # Parse the date field.
        #
        try:
            trip.date_start, trip.date_end = self.parse_date(trip_date_str)
        except Exception:
            raise PageFormatException(trip_link, "trip date parse")
        is_in_past = trip.date_end < datetime.date.today()

        #
        # Find the route name and link.
        # The link to the route has a constant text, so we can find it by that.
        # The name is found by assumed relative position in a parent element.
        #
        is_route_found = False
        try:
            route_el = self._driver.find_element(By.LINK_TEXT, "See full route/place details.")
            is_route_found = True
        except Exception:
            pass
        if is_route_found:
            trip.route_url = route_el.get_attribute("href")
            try:
                pel = route_el.find_element(By.XPATH, "../../..")
                trip.route_name = pel.find_element(By.TAG_NAME, "h3").text
            except Exception:
                raise PageFormatException(trip_link, "trip route name navigation")

        #
        # Trip status
        #
        result_error_el: WebElement | None = None
        result_error_text: str = ""
        register_el: WebElement | None = None
        register_text: str = ""
        try:
            result_error_el = self._driver.find_element(By.XPATH, "//div[@class='error']")
            result_error_text = result_error_el.text
        except Exception:
            pass
        try:
            register_el = self._driver.find_element(By.XPATH, "//div[@id='register-participant']")
            register_text = register_el.text
        except Exception: 
            pass

        if result_error_text:
            #
            # CASE:  found an item for closed trips.
            #     
            if "has been closed" in result_error_text:
                trip.status = ACTIVITY_STATUS_CLOSED
                if "successful" in result_error_text:
                    trip.result = ACTIVITY_RESULT_SUCCESS
                elif "canceled" in result_error_text:
                    trip.result = ACTIVITY_RESULT_CANCELED
                elif "turned around" in result_error_text:
                    trip.result = ACTIVITY_RESULT_TURNED_AROUND               
                else:
                    trip.result = result_error_text.replace("This activity has been closed. ", "").strip()
            elif 'This event has been canceled.' in result_error_text:
                trip.status = ACTIVITY_STATUS_CLOSED
                trip.result = ACTIVITY_RESULT_CANCELED            
            elif 'This event already ended' in result_error_text:
                # Events don't have result so assume success.
                trip.status = ACTIVITY_STATUS_CLOSED
                trip.result = ACTIVITY_RESULT_SUCCESS
            elif 'This activity already ended.' in result_error_text:
                 # An activity that has not been closed is marked in the past with no result.  It could yet change.
                 trip.status = ACTIVITY_STATUS_CLOSED
                 trip.result = ACTIVITY_RESULT_SUCCESS
            elif 'Registration closed on' in result_error_text:
                 # Registration has closed but the trip has not run?
                 trip.status = ACTIVITY_STATUS_PAST if is_in_past else ACTIVITY_STATUS_FUTURE
            else:
                # TODO:  Write error to log
                # Another error:  You have a date conflict with another activity where you registered previously.
                #   seen on: https://www.mountaineers.org/activities/activities/sea-kayak-skagit-hope-islands-65
                # Should look for the "Register"/ "Register for waitlist" button and see if it is disabled.
                trip.status = ACTIVITY_STATUS_PAST if is_in_past else ACTIVITY_STATUS_FUTURE
        else:
            if "This activity is part of the" in register_text:
                #
                # CASE: part of a class.  Some show as closed and others do not.
                # Either way, treat them as closed.
                #
                if is_in_past:
                    trip.status = ACTIVITY_STATUS_CLOSED
                    trip.result = ACTIVITY_RESULT_SUCCESS
                else:
                   trip.status = ACTIVITY_STATUS_FUTURE                   
            else:
                #
                # Otherwise, an activity that is not marked as closed.  
                # I'll mark it as past.  
                # This is different than course field trip logic.  Both probably need some logic 
                # to retry until a couple months have elapsed and then just declare them closed.
                #
                trip.status = ACTIVITY_STATUS_PAST if is_in_past else ACTIVITY_STATUS_FUTURE
                trip.result = ACTIVITY_RESULT_SUCCESS if is_in_past else ""
  


        #
        # Participants
        #
        # Find the roster element
        try:
            roster_el = self._driver.find_element(By.XPATH, "//div[@data-tab='roster-tab']")
        except Exception:
            raise PageFormatException(trip_link, "roster tab not found")

        # click on it.
        try:
            roster_el.click()
        except ElementNotInteractableException as e:
            raise WebResponseException(trip_link, "click on roster - element not interactable") from e


        #
        # Wait for the roster to load
        #
        if not self.wait_for_element1(self._driver, By.XPATH, "//div[@class='tabs']/div[@data-tab='roster-tab']/div[@class='tab-content']/h3", 60):
            raise PageFormatException(trip_link, "roster tab not loaded")
        time.sleep(2)

        participants = set()
        div_list = roster_el.find_elements(By.XPATH, "//div[@class='roster-contact']")
        for div_el in div_list:
            #
            # Canceled trips may have the leader but no other members.  However,
            # more than just the leader <div> is present.  
            #
            is_member_found = False
            try:
                # Look for member link.
                member_link_el = div_el.find_element(By.TAG_NAME, "a")
                is_member_found = True
            except Exception:
                # Sometimes there are empty entries in the list.  Skip over them
                continue

            if is_member_found:
                member = ScrapedActivityMember()
                member.activity_url = trip.url
                member.activity_name = trip.name
                member.member_url = member_link_el.get_attribute("href").replace("?ajax_load=1","")
                member.member_name = member_link_el.text.title()
                try:
                    roster_position_el = div_el.find_element(By.CLASS_NAME, "roster-position")
                    member.role = roster_position_el.text
                except Exception:
                    member.role = "Participant"

                member.registration = MEMBER_STATUS_REGISTERED
                member.is_canceled = False
                member.activity_url = trip_link

                if member.member_url not in participants:
                    participants.add(member.member_url)
                    trip.participants.append(member)
        
        return trip


-- select * from person p1
-- join person p2 on p1.profile_url = p2.profile_url
-- where p1.id != p2.id

-- select * from person p1
-- join activitymember am1 on p1.id = am1.person_id
-- join activity ac1 on am1.activity_id = ac1.id
-- where p1.id = 2267 

-- select * from activity as act
-- join activitymember as am on act.id = am.activity_id
-- join person as p on am.person_id = p.id
-- where act.id = 679

select * from activitymember as am
join person as p on am.person_id = p.id
join activity as act on am.activity_id = act.id
where am.id = 6


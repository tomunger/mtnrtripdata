ALTER TABLE "user" RENAME TO "person";
-- Rename the table "user" to "person"
ALTER TABLE user RENAME TO person;

-- Update foreign key references in "activitymember" table
ALTER TABLE activitymember DROP CONSTRAINT activitymember_user_id_fkey;
ALTER TABLE activitymember ADD CONSTRAINT activitymember_person_id_fkey FOREIGN KEY (person_id) REFERENCES person(id) ON DELETE CASCADE;


 * Table User
   * rename object User to Person x
   * rename table "user" to "person"  x
   * Add index on user name and full name x
 * Table ActivityMember
   * change field "user_id" to "person_id"
   * change field "user" to "person" x
   * change foreign key "user_id"
 * Table Activity
   * Add index on date_start, date_end, activity_type, status,
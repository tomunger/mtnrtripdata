# Database Import

After adminer export and import, the auto increment primary keys are set incorrectly.  The
following will set them at the max value.

    SELECT setval('activity_id_seq', (SELECT max(id) FROM activity));
    SELECT setval('activitymember_id_seq', (SELECT max(id) FROM activitymember));
    SELECT setval('person_id_seq', (SELECT max(id) FROM person));
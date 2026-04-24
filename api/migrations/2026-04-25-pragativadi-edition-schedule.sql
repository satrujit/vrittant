-- 2026-04-25-pragativadi-edition-schedule.sql
-- Seeds Pragativadi with 6 daily editions + Sunday-only Avimat.
-- Editions 2-5 carry the four supplement pages pg_A..pg_D.
-- Edition 6 collapses A-D into pg_13..pg_16.

UPDATE org_configs
SET edition_schedule = '[
  {"name":"Ed 1","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"}
  ]},
  {"name":"Ed 2","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 3","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 4","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 5","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 6","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_13"},{"page_number":14,"page_name":"pg_14"},
    {"page_number":15,"page_name":"pg_15"},{"page_number":16,"page_name":"pg_16"}
  ]},
  {"name":"Avimat","weekdays":[6],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"}
  ]}
]'::jsonb
WHERE organization_id = (SELECT id FROM organizations WHERE name ILIKE '%pragativadi%' LIMIT 1);

SELECT value as kwh, date as timestamp, r.tariff_block_name  from reading r where ref =:itish_elec order by date desc

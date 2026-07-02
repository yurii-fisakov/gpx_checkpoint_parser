# README Report Example Design

## Goal

Keep the README output example aligned with the current generated report.

## Change

Replace the existing single-checkpoint, single-rider CSV block under
`The script creates report.csv` with the complete current contents of
`report.csv`:

```csv
user_name,Ставчены,Грушевский родник,Поворот на ВлВ,Круг ВлВ
Oleg Sat,05:29:15,05:46:03,06:07:42,06:15:33
Игорь Артемов,07:06:41,07:25:29,07:57:11,08:09:36
Юра Фисаков,05:29:06,05:45:19,06:07:42,06:15:14
```

No other README content or application behavior changes. Existing local
script, test, configuration, file-mode, and GPX changes remain untouched.

## Verification

Extract the README CSV block and compare it byte-for-byte with `report.csv`
after normalizing line endings.

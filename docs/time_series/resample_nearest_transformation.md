# Resample nearest transformation

Name: `resample_nearest`

This transformation manipulates timestamp values and finds the nearest signal value for each new timestamp.

## Input parameters

| Name            | Required |             Default value             | Description                                                          |
|-----------------|:--------:|:-------------------------------------:|----------------------------------------------------------------------|
| period          |   Yes    |                                       | New time interval between new timestamps                             |
| start_timestamp |    No    |                   0                   | The first of the new timestamp value                                 |
| end_timestamp   |    No    | period + the greatest input timestamp | The last of the new timestamp values will be less than end_timestamp |

## Additional remarks

- this transformation allows to transform only one time series at the same time
- output time series type is always `Timestamp`
- if two signal values have the same difference, earlier is used

## Examples

### Example 1

Input parameters:

- period = 5

| Timestamp | Signal value |
|-----------|--------------|
| 1         | 10           |
| 7         | 20           |
| 14        | 30           |
| 20        | 40           |

Output:

| Timestamp | Signal value |
|-----------|--------------|
| 0         | 10           |
| 5         | 20           |
| 10        | 20           |
| 15        | 30           |
| 20        | 40           |

### Example 2

Input parameters:

- period = 2
- start_timestamp = 10
- end_timestamp = 20

| Begin timestamp | End timestamp | Signal value |
|-----------------|---------------|--------------|
| 1               | 2             | 10           |
| 7               | 10            | 20           |
| 14              | 18            | 30           |
| 20              | 25            | 40           |

Output:

| Timestamp | Signal value |
|-----------|--------------|
| 10        | 20           |
| 12        | 20           |
| 14        | 30           |
| 16        | 30           |
| 18        | 30           |
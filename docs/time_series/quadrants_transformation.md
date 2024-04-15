# Quadrants transformation

Name: `quadrants`

This transformation use two signal values (X, Y) with the same timestamps and calculate quadrant. The default origin
point is (0, 0) but it can be changed with parameters.

## Input parameters

| Name     | Required | Default value | Description                                      |
|----------|:--------:|:-------------:|--------------------------------------------------|
| origin_x |    No    |       0       | X value of the center point of coordinate system |
| origin_y |    No    |       0       | Y value of the center point of coordinate system |

## Additional remarks

- this transformation allows to transform only two time series at the same time
- types of time series should be equal
- output time series type is the same as input time series
- signal values with not matching timestamps will be omitted
- if the signal value equals origin value (is on axis), the signal value will be interpreted as `signal_value + epsilon`

## Examples

### Example 1

Input parameters:

| Timestamp | Signal value X | Signal value Y |
|-----------|----------------|----------------|
| 2         | 5              | 3              |
| 4         | -5             | 3              |
| 6         | -5             | -3             |
| 8         | 5              | -3             |

Output:

| Timestamp | Signal value |
|-----------|--------------|
| 2         | 1            |
| 4         | 2            |
| 6         | 3            |
| 8         | 4            |

### Example 2

Input parameters:

- origin_x = -10
- origin_y = -10

| Begin timestamp | End timestamp | Signal value X | Signal value Y |
|-----------------|---------------|----------------|----------------|
| 0               | 1             | 5              | 3              |
| 5               | 6             |                | 3              |
| 10              | 11            | -5             | -3             |
| 15              | 16            | 5              |                |

Output:

| Begin timestamp | End timestamp | Signal value |
|-----------------|---------------|--------------|
| 0               | 1             | 1            |
| 10              | 11            | 1            |
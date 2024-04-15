# How to create custom transformation

1. Create new class in `grisera_api/time_series/transformation` directory. New class should
   extend `TimeSeriesTransformation` base class.
2. Add new `TransformationType` enum value in `grisera_api/time_series/time_series_model.py`. Transformation name enum
   value will be used in POST request.
3. Register new class in `get_transformation` method
   in `grisera_api/time_series/transformation/TimeSeriesTransformationFactory.py` using new enum value.
4. Implement `def transform` method. This method should return tuple of new `TimeSeriesIn` object
   and `new_signal_values_id_mapping` list. Each `new_signal_values_id_mapping` value represent list of source signal
   value ids for every new signal value. This mapping is necessary to create `basedOn` relationships between new and
   source signal values. Bellow is simple transformation example implementation.

```python
class TimeSeriesTransformationMultiplication(TimeSeriesTransformation):
    """
    Class with logic of time series multiplication transformation

    """

    def transform(self, time_series: List[TimeSeriesOut], additional_properties: Optional[List[PropertyIn]]):
        """
        Transform time series data.

        Multiply every signal value by `multiplier` additional input parameter.
        If parameter does not exist default value is 10

        Args:
            time_series (List[TimeSeriesOut]): Time series to be transformed
            additional_properties (Optional[List[PropertyIn]]): Transformation parameters

        Returns:
            New time series object
        """
        assert len(time_series) == 1, "Number of time series should equals 1 for multiplication transformation"
        multiplier = get_additional_parameter(additional_properties, "multiplier")
        multiplier = int(multiplier) if multiplier is not None else 10

        if additional_properties is None:
            additional_properties = []
        additional_properties.append(PropertyIn(key="transformation_name", value=TransformationType.MULTIPLICATION))

        new_signal_values = []
        new_signal_values_id_mapping = []
        # Iterate over all signal values
        for current_signal_value in time_series[0].signal_values:
            product = int(get_node_property(current_signal_value["signal_value"], "value")) * multiplier
            new_signal_values.append(SignalIn(signal_value=SignalValueNodesIn(value=product),
                                              timestamp=get_node_property(
                                                  current_signal_value["timestamp"], "timestamp"),
                                              start_timestamp=get_node_property(
                                                  current_signal_value["timestamp"], "start_timestamp"),
                                              end_timestamp=get_node_property(
                                                  current_signal_value["timestamp"], "end_timestamp"),
                                              ))
            new_signal_values_id_mapping.append([current_signal_value["signal_value"]["id"]])
        return TimeSeriesIn(type=time_series[0].type,
                            additional_properties=additional_properties,
                            signal_values=new_signal_values
                            ), new_signal_values_id_mapping
```

5. Create new unit test class
   in `grisera_api/tests/tests_graphdb_with_signal_values/tests_time_series/tests_transformation` directory. Bellow is
   simple unit test for multiplication transformation.

```python
class TestTimeSeriesTransformationMultiplication(unittest.TestCase):
    time_series_timestamp = [
        TimeSeriesOut(
            type=Type.timestamp,
            signal_values=[
                {
                    'signal_value': {'labels': ['Signal Value'], 'id': 2,
                                     'properties': [{'key': 'value', 'value': 10}]},
                    'timestamp': {'labels': ['Timestamp'], 'id': 1, 'properties': [
                        {'key': 'timestamp', 'value': 0}]}
                },
                {
                    'signal_value': {'labels': ['Signal Value'], 'id': 4,
                                     'properties': [
                                         {'key': 'value', 'value': 20}]},
                    'timestamp': {'labels': ['Timestamp'], 'id': 3, 'properties': [
                        {'key': 'timestamp', 'value': 5}]}
                },
                {
                    'signal_value': {'labels': ['Signal Value'], 'id': 6,
                                     'properties': [
                                         {'key': 'value', 'value': 30}]},
                    'timestamp': {'labels': ['Timestamp'], 'id': 5, 'properties': [
                        {'key': 'timestamp', 'value': 10}]}
                }
            ])
    ]

    def test_transform_timestamp(self):
        additional_properties = [PropertyIn(key="multiplier", value=2)]

        time_series_transformation = TimeSeriesTransformationMultiplication()
        result = time_series_transformation.transform(self.time_series_timestamp, additional_properties)

        self.assertEqual(
            (
                TimeSeriesIn(
                    type=Type.timestamp,
                    signal_values=[
                        SignalIn(timestamp=0, signal_value=SignalValueNodesIn(value=20)),
                        SignalIn(timestamp=5, signal_value=SignalValueNodesIn(value=40)),
                        SignalIn(timestamp=10, signal_value=SignalValueNodesIn(value=60))
                    ],
                   additional_properties=[
                      PropertyIn(key='multiplier', value='2'),
                      PropertyIn(key='transformation_name', value='multiplication')
                   ]
                ),
                [[2], [4], [6]]
            ),
           result)
```

6. Write documentation in `grisera_api/docs/time_series` directory.
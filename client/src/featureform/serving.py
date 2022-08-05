# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import json
import marshal
import os
import random
import types

import grpc
import numpy as np
from featureform.proto import serving_pb2
from featureform.proto import serving_pb2_grpc
from .tls import insecure_channel, secure_channel
import pandas as pd
from .sqlite_metadata import SQLiteMetadata

class Client:

    def __init__(self, host=None, local=False, insecure=False, cert_path=None):
        if local and host:
            raise ValueError("Host and local cannot both be set")
        if local:
            self.impl = LocalClientImpl()
        else:
            self.impl = HostedClientImpl(host, insecure, cert_path)


    def training_set(self, name, version):
        return self.impl.training_set(name, version)

    def features(self, features, entities):
        return self.impl.features(features, entities)

    def process_feature_csv(self, source_path, entity_name, entity_col, value_col, dataframe_mapping,
                            feature_name_variant, timestamp_column):
        return self.impl.process_feature_csv(source_path, entity_name, entity_col, value_col, dataframe_mapping, feature_name_variant, timestamp_column)

    def label_df_from_csv(self, source_path, entity_name, entity_col, value_col, timestamp_column):
        return self.impl.label_df_from_csv(source_path, entity_name, entity_col, value_col, timestamp_column)

class HostedClientImpl:
    def __init__(self, host=None, insecure=False, cert_path=None):
        host = host or os.getenv('FEATUREFORM_HOST')
        if host is None:
            raise ValueError(
                'If not in local mode then `host` must be passed or the environment'
                ' variable FEATUREFORM_HOST must be set.'
            )
        channel = self._create_channel(host, insecure, cert_path)
        self._stub = serving_pb2_grpc.FeatureStub(channel)

    def _create_channel(self, host, insecure, cert_path):
        if insecure:
            return self._create_insecure_channel(host)
        else:
            return self._create_secure_channel(host, cert_path)  

    def _create_insecure_channel(self, host):
        return grpc.insecure_channel(host, options=(('grpc.enable_http_proxy', 0),))

    def _create_secure_channel(self, host, cert_path):
        cert_path = cert_path or os.getenv('FEATUREFORM_CERT')
        use_default_creds = not cert_path
        if use_default_creds:
            credentials = grpc.ssl_channel_credentials()
        else:
            with open(cert_path, 'rb') as f:
                credentials = grpc.ssl_channel_credentials(f.read())
        return grpc.secure_channel(host, credentials)

    def training_set(self, name, version):
        return Dataset(self._stub).from_stub(name, version)

    def features(self, features, entities):
        req = serving_pb2.FeatureServeRequest()
        for name, value in entities.items():
            entity_proto = req.entities.add()
            entity_proto.name = name
            entity_proto.value = value
        for (name, version) in features:
            feature_id = req.features.add()
            feature_id.name = name
            feature_id.version = version
        resp = self._stub.FeatureServe(req)
        return [parse_proto_value(val) for val in resp.values]

class LocalClientImpl:
    def __init__(self):
        self.db = SQLiteMetadata()
        
    def training_set(self, training_set_name, training_set_variant):
        training_set = self.db.get_training_set_variant(training_set_name, training_set_variant)
        label = self.db.get_label_variant(training_set['label_name'], training_set['label_variant'])
        label_df = self.get_label_dataframe(label)
        # We will build the training set DF by merging each feature one by one into it.
        trainingset_df = label_df
        features = self.db.get_training_set_features(training_set_name, training_set_variant)
        for feature_variant in features:
            feature = self.db.get_feature_variant(feature_variant['feature_name'], feature_variant['feature_variant'])
            feature_df = self.get_feature_dataframe(feature)
            trainingset_df = self.merge_feature_into_ts(feature, label, feature_df, trainingset_df)

        return self.convert_ts_df_to_dataset(label, trainingset_df)

    def process_transformation(self, name, variant):
        source_row = self.db.get_source_variant(name, variant)
        inputs = json.loads(source_row['inputs'])
        dataframes = []
        code = marshal.loads(bytearray(source_row['definition']))
        func = types.FunctionType(code, globals(), "transformation")
        for input in inputs:
            source_name, source_variant = input[0], input[1],
            if self.db.is_transformation(source_name, source_variant):
                df = self.process_transformation(source_name, source_variant)
                dataframes.append(df)
            else:
                source_row = \
                    self.db.get_source_variant(source_name, source_variant)
                df = pd.read_csv(str(source_row['definition']))
                dataframes.append(df)
        new_data = func(*dataframes)
        return new_data

    def get_label_dataframe(self, label):
        if self.db.is_transformation(label['source_name'], label['source_variant']):
            label_df = self.label_df_from_transformation(label) 
        else:
            label_df = self.label_df_from_csv(label)
        label_df.rename(columns={label['source_value']: 'label'}, inplace=True)
        return label_df

    def label_df_from_transformation(self, label):
        df = self.process_transformation(label['source_name'], label['source_variant'])
        if label['source_timestamp'] != "":
            df = df[[label['source_entity'], label['source_value'], label['source_timestamp']]]
            df[label['source_timestamp']] = pd.to_datetime(df[label['source_timestamp']])
        else:
            df = df[[label['source_entity'], label['source_value']]]
        df.set_index(label['source_entity'])
        return df

    def label_df_from_csv(self, label):
        label_source = self.db.get_source_variant(label['source_name'], label['source_variant'])
        df = pd.read_csv(label_source['definition'])
        if label['source_entity'] not in df.columns:
            raise KeyError(f"Entity column does not exist: {label['source_entity']}")
        if label['source_value'] not in df.columns:
            raise KeyError(f"Value column does not exist: {label['source_value']}")
        if label['source_timestamp'] != "" and label['source_timestamp'] not in df.columns:
            raise KeyError(f"Timestamp column does not exist: {label['source_timestamp']}")
        if label['source_timestamp'] != "":
            df = df[[label['source_entity'], label['source_value'], label['source_timestamp']]]
            df[label['source_timestamp']] = pd.to_datetime(df[label['source_timestamp']])
            df.sort_values(by=label['source_timestamp'], inplace=True)
            df.drop_duplicates(subset=[label['source_entity'], label['source_timestamp']], keep="last", inplace=True)
        else:
            df = df[[label['source_entity'], label['source_value']]]  
        df.rename(columns={label['source_entity']: label['source_entity']}, inplace=True)
        df.set_index(label['source_entity'], inplace=True)
        return df

    def get_feature_dataframe(self, feature):
        name_variant = feature['name'] + "." + feature['variant']
        if self.db.is_transformation(feature['source_name'], feature['source_variant']):
            feature_df = self.feature_df_from_transformation(feature)
        else:
            feature_df = self.feature_df_from_csv(feature)
        feature_df.set_index(feature['source_entity'])
        feature_df.rename(columns={feature['source_value']: name_variant}, inplace=True)
        return feature_df

    def feature_df_from_transformation(self, feature):
        df = self.process_transformation(feature['source_name'], feature['source_variant'])
        if isinstance(df, pd.Series):
            df = df.to_frame()
            df.reset_index(inplace=True)
        if feature['source_timestamp'] != "":
            df = df[[feature['source_entity'], feature['source_value'], feature['source_timestamp']]]
            df[feature['source_timestamp']] = pd.to_datetime(df[feature['source_timestamp']])
        else:
            df = df[[feature['source_entity'], feature['source_value']]]
        return df

    def feature_df_from_csv(self, feature):
        source = self.db.get_source_variant(feature['source_name'], feature['source_variant'])
        df = pd.read_csv(str(source['definition']))
        if feature['source_timestamp'] != "":
            df = df[[feature['source_entity'], feature['source_value'], feature['source_timestamp']]]
            df[feature['source_timestamp']] = pd.to_datetime(df[feature['source_timestamp']])
        else:
            df = df[[feature['source_entity'], feature['source_value']]]
        return df

    def merge_feature_into_ts(self, feature_row, label_row, df, trainingset_df):
        if feature_row['source_timestamp'] != "":
            trainingset_df = pd.merge_asof(trainingset_df, df.sort_values(['ts']), direction='backward',
                                            left_on=label_row['source_timestamp'], right_on=feature_row['source_timestamp'], left_by=label_row['source_entity'],
                                            right_by=feature_row['source_entity'])
        else:
            df.drop_duplicates(subset=[feature_row['source_entity']], keep="last", inplace=True)
            trainingset_df.reset_index(inplace=True)
            trainingset_df[label_row['source_entity']] = trainingset_df[label_row['source_entity']].astype('string')
            df[label_row['source_entity']] = df[label_row['source_entity']].astype('string')
            trainingset_df = trainingset_df.join(df.set_index(label_row['source_entity']), how="left", on=label_row['source_entity'],
                                                    lsuffix="_left")
            if "index" in trainingset_df.columns:
                trainingset_df.drop(columns='index', inplace=True)
        return trainingset_df

    def convert_ts_df_to_dataset(self, label_row, trainingset_df):
        if label_row['source_timestamp'] != "":
            trainingset_df.drop(columns=label_row['source_timestamp'], inplace=True)
        trainingset_df.drop(columns=label_row['source_entity'], inplace=True)

        label_col = trainingset_df.pop('label')
        trainingset_df = trainingset_df.assign(label=label_col)
        return Dataset.from_list(trainingset_df.values.tolist())

    def features(self, feature_variant_list, entity):
        if len(feature_variant_list) == 0:
            raise Exception("No features provided")
        # This code was originally written to take a tuple, this is a quick fix to turn a dict with a single entry into that tuple.
        # This should all be refactored later.
        entity_tuple = list(entity.items())[0]
        dataframe_mapping = []
        all_feature_df = None
        for featureVariantTuple in feature_variant_list:

            feature_row = self.db.get_feature_variant(featureVariantTuple[0], featureVariantTuple[1])
            entity_column, ts_column, feature_column_name, source_name, source_variant = feature_row['source_entity'], feature_row['source_timestamp'], feature_row['source_value'], feature_row['source_name'], feature_row['source_variant']

            source_row = self.db.get_source_variant(source_name, source_variant)
            if self.db.is_transformation(source_name, source_variant):
                df = self.process_transformation(source_name, source_variant)
                if isinstance(df, pd.Series):
                    df = df.to_frame()
                    df.reset_index(inplace=True)
                df = df[[entity_tuple[0], feature_column_name]]
                df.set_index(entity_tuple[0])
                dataframe_mapping.append(df)
            else:
                name_variant = f"{featureVariantTuple[0]}.{featureVariantTuple[1]}"
                dataframe_mapping = self.process_feature_csv(source_row['definition'], entity_tuple[0], entity_column,
                                                             feature_column_name,
                                                             dataframe_mapping,
                                                             name_variant, ts_column)
        try:
            for value in dataframe_mapping:
                if all_feature_df is None:
                    all_feature_df = value
                else:
                    all_feature_df = all_feature_df.join(value.set_index(entity_tuple[0]), on=entity_tuple[0],
                                                         lsuffix='_left')
        except TypeError:
            print("Set is empty")
        entity_row = all_feature_df.loc[all_feature_df[entity_tuple[0]] == entity_tuple[1]].copy()
        entity_row.drop(columns=entity_tuple[0], inplace=True)
        if len(entity_row.values) > 0:
            return entity_row.values[0]
        else:
            raise Exception("No matching entities for {}".format(entity_tuple))

    def process_feature_csv(self, source_path, entity_name, entity_col, value_col, dataframe_mapping,
                            feature_name_variant, timestamp_column):
        df = pd.read_csv(str(source_path))
        if entity_col not in df.columns:
            raise KeyError(f"Entity column does not exist: {entity_col}")
        if value_col not in df.columns:
            raise KeyError(f"Value column does not exist: {value_col}")
        if timestamp_column != "" and timestamp_column not in df.columns:
            raise KeyError(f"Timestamp column does not exist: {timestamp_column}")
        if timestamp_column != "":
            df = df[[entity_col, value_col, timestamp_column]]
        else:
            df = df[[entity_col, value_col]]
        df.set_index(entity_col)
        if timestamp_column != "":
            df = df.sort_values(by=timestamp_column, ascending=True)
        df.rename(columns={entity_col: entity_name, value_col: feature_name_variant}, inplace=True)
        df.drop_duplicates(subset=[entity_name], keep="last", inplace=True)

        if timestamp_column != "":
            df = df.drop(columns=timestamp_column)
        dataframe_mapping.append(df)
        return dataframe_mapping

class Stream:

    def __init__(self, stub, name, version):
        req = serving_pb2.TrainingDataRequest()
        req.id.name = name
        req.id.version = version
        self.name = name
        self.version = version
        self._stub = stub
        self._req = req
        self._iter = stub.TrainingData(req)

    def __iter__(self):
        return self

    def __next__(self):
        return Row(next(self._iter))

    def restart(self):
        self._iter = self._stub.TrainingData(self._req)


class LocalStream:

    def __init__(self, datalist):
        self._datalist = datalist
        self._iter = iter(datalist)

    def __iter__(self):
        return iter(self._iter)

    def __next__(self):
        return LocalRow(next(self._iter))

    def restart(self):
        self._iter = iter(self._datalist)


class Repeat:

    def __init__(self, repeat_num, stream):
        self.repeat_num = repeat_num
        self._stream = stream

    def __iter__(self):
        return self

    def __next__(self):
        try:
            next_val = next(self._stream)
        except StopIteration:
            self.repeat_num -= 1
            if self.repeat_num >= 0:
                self._stream.restart()
                next_val = next(self._stream)
            else:
                raise

        return next_val


class Shuffle:

    def __init__(self, buffer_size, stream):
        self.buffer_size = buffer_size
        self._shuffled_data_list = []
        self._stream = stream
        self.__setup_buffer()

    def __setup_buffer(self):
        try:
            for _ in range(self.buffer_size):
                self._shuffled_data_list.append(next(self._stream))
        except StopIteration:
            pass

    def restart(self):
        self._stream.restart()
        self.__setup_buffer()

    def __iter__(self):
        return self

    def __next__(self):
        if len(self._shuffled_data_list) == 0:
            raise StopIteration
        random_index = random.randrange(len(self._shuffled_data_list))
        next_row = self._shuffled_data_list.pop(random_index)

        try:
            self._shuffled_data_list.append(next(self._stream))
        except StopIteration:
            pass

        return next_row


class Batch:

    def __init__(self, batch_size, stream):
        self.batch_size = batch_size
        self._stream = stream

    def restart(self):
        self._stream.restart()

    def __iter__(self):
        return self

    def __next__(self):
        rows = BatchRow()
        for _ in range(self.batch_size):
            try:
                next_row = next(self._stream)
                rows.append(next_row)
            except StopIteration:
                if len(rows) == 0:
                    raise
                return rows
        return rows


class Dataset:
    def __init__(self, stream):
        self._stream = stream

    def from_stub(self, name, version):
        stream = Stream(self._stream, name, version)
        return Dataset(stream)

    def from_list(datalist):
        stream = LocalStream(datalist)
        return Dataset(stream)

    def repeat(self, num):
        if num <= 0:
            raise Exception("Must repeat 1 or more times")
        self._stream = Repeat(num, self._stream)
        return self

    def shuffle(self, buffer_size):
        if buffer_size <= 0:
            raise Exception("Buffer size must be greater than or equal to 1")
        self._stream = Shuffle(buffer_size, self._stream)
        return self

    def batch(self, batch_size):
        if batch_size <= 0:
            raise Exception("Batch size must be greater than or equal to 1")
        self._stream = Batch(batch_size, self._stream)
        return self

    def __iter__(self):
        return self

    def __next__(self):
        next_val = next(self._stream)
        return next_val


class Row:

    def __init__(self, proto_row):
        features = np.array(
            [parse_proto_value(feature) for feature in proto_row.features])
        self._label = parse_proto_value(proto_row.label)
        self._row = np.append(features, self._label)

    def features(self):
        return self._row[:-1]

    def label(self):
        return self._label

    def to_numpy(self):
        return self._row()

    def __repr__(self):
        return "Features: {} , Label: {}".format(self.features(), self.label())


class LocalRow:

    def __init__(self, row_list):
        self._features = row_list[:-1]
        self._row = row_list
        self._label = row_list[-1]

    def features(self):
        return self._features

    def label(self):
        return self._label

    def to_numpy(self):
        return np.array(self._row)

    def __repr__(self):
        return "Features: {} , Label: {}".format(self.features(), self.label())

class BatchRow:

    def __init__(self, rows=None):
        self._features = []
        self._labels = []
        if rows is None:
            rows = []
        self._rows = rows
        for row in rows:
            self.append(row)

    def append(self, row):
        self._features.append(row.features())
        self._labels.append(row.label())
        self._rows.append(row)

    def features(self):
        return self._features

    def labels(self):
        return self._labels

    def to_list(self):
        return self._rows

    def __len__(self):
        return len(self._rows)

def parse_proto_value(value):
    """ parse_proto_value is used to parse the one of Value message
	"""
    return getattr(value, value.WhichOneof("value"))

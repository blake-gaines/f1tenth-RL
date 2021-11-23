import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, initializers, losses, optimizers, regularizers

def build_dense(state_size, history_length, num_actions, learning_rate):
    inputs = tf.keras.Input(shape=(state_size, history_length))
    x = layers.Dense(128, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(inputs)
    x = layers.Dense(128, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    x = layers.Flatten()(x)
    predictions = layers.Dense(num_actions, activation='linear', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    model = tf.keras.Model(inputs=inputs, outputs=predictions)
    model.compile(optimizer=optimizers.Adam(learning_rate),
                        loss=losses.Huber()) #loss to be removed. It is needed in the bugged version installed on Jetson
    model.summary()
    return model

def build_cnn1D(state_size, history_length, num_actions, learning_rate):
    inputs = tf.keras.Input(shape=(state_size, history_length))
    x = layers.Conv1D(filters=16, kernel_size=4, strides=2, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(inputs)
    x = layers.Conv1D(filters=32, kernel_size=2, strides=1, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    x = layers.Flatten()(x)
    x = layers.Dense(64, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    predictions = layers.Dense(num_actions, activation='linear', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    model = tf.keras.Model(inputs=inputs, outputs=predictions)
    model.compile(optimizer=optimizers.Adam(learning_rate),
                        loss=losses.Huber()) #loss to be removed. It is needed in the bugged version installed on Jetson
    model.summary()
    return model

def build_cnn1D_plus_velocity(state_size, history_length, num_actions, learning_rate):
    inputs = tf.keras.Input(shape=(state_size, history_length), name="lidar")
    input_acceleration = tf.keras.Input(shape=((history_length)), name="acc")
    x = layers.Conv1D(filters=16, kernel_size=4, strides=2, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(inputs)
    x = layers.Conv1D(filters=32, kernel_size=2, strides=1, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    x = layers.Flatten()(x)
    x = layers.concatenate([x, input_acceleration])
    x = layers.Dense(64, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    predictions = layers.Dense(num_actions, activation='linear', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    model = tf.keras.Model(inputs=[inputs, input_acceleration], outputs=predictions)
    model.compile(optimizer=optimizers.Adam(learning_rate),
                        loss=losses.Huber()) #loss to be removed. It is needed in the bugged version installed on Jetson
    model.summary()
    return model

def build_cnn2D(image_width, image_height, history_length, num_actions, learning_rate):
    inputs = tf.keras.Input(shape=(image_width, image_height, history_length))
    x = layers.Lambda(lambda layer: layer / 255)(inputs)
    x = layers.Conv2D(filters=16, kernel_size=(4, 4), strides=(2, 2), activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    x = layers.MaxPool2D((2,2))(x)
    x = layers.Conv2D(filters=8, kernel_size=(2, 2), strides=(1, 1), activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    x = layers.MaxPool2D((2,2))(x)
    x = layers.Flatten()(x)
    x = layers.Dense(64, activation='relu', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    predictions = layers.Dense(num_actions, activation='linear', kernel_initializer=initializers.VarianceScaling(scale=2.))(x)
    model = tf.keras.Model(inputs=inputs, outputs=predictions)
    model.compile(optimizer=optimizers.Adam(learning_rate),
                        loss=losses.Huber()) #loss to be removed. It is needed in the bugged version installed on Jetson
    model.summary()
    return model






#####################################
# PointNet (source: https://keras.io/examples/vision/pointnet/)
#####################################

def build_pointnet(state_size, features, history_length, num_actions, learning_rate):
    channels = features * history_length
    inputs = tf.keras.Input(shape=(state_size, channels))
    x = tnet(inputs, channels)
    x = conv_bn(x, 32)
    x = conv_bn(x, 32)
    x = tnet(x, 32)
    x = conv_bn(x, 32)
    x = conv_bn(x, 64)
    x = conv_bn(x, 512)
    x = layers.GlobalMaxPooling1D()(x)
    x = dense_bn(x, 256)
    x = layers.Dropout(0.3)(x)
    x = dense_bn(x, 128)
    x = layers.Dropout(0.3)(x)
    x = layers.Flatten()(x)
    outputs = layers.Dense(num_actions, activation="linear")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="pointnet")
    model.compile(optimizer=optimizers.Adam(learning_rate),
                        loss=losses.Huber()) #loss to be removed. It is needed in the bugged version installed on Jetson
    model.summary()
    return model

def conv_bn(x, filters):
    x = layers.Conv1D(filters, kernel_size=1, padding="valid")(x)
    x = layers.BatchNormalization(momentum=0.0)(x)
    return layers.Activation("relu")(x)


def dense_bn(x, filters):
    x = layers.Dense(filters)(x)
    x = layers.BatchNormalization(momentum=0.0)(x)
    return layers.Activation("relu")(x)

class OrthogonalRegularizer(regularizers.Regularizer):
    def __init__(self, num_features, l2reg=0.001):
        self.num_features = num_features
        self.l2reg = l2reg
        self.eye = tf.eye(num_features)

    def __call__(self, x):
        x = tf.reshape(x, (-1, self.num_features, self.num_features))
        xxt = tf.tensordot(x, x, axes=(2, 2))
        xxt = tf.reshape(xxt, (-1, self.num_features, self.num_features))
        return tf.reduce_sum(self.l2reg * tf.square(xxt - self.eye))

def tnet(inputs, num_features):

    # Initalise bias as the indentity matrix
    bias = initializers.Constant(np.eye(num_features).flatten())
    reg = OrthogonalRegularizer(num_features)

    x = conv_bn(inputs, 32)
    x = conv_bn(x, 64)
    x = conv_bn(x, 512)
    x = layers.GlobalMaxPooling1D()(x)
    x = dense_bn(x, 256)
    x = dense_bn(x, 128)
    x = layers.Dense(
        num_features * num_features,
        kernel_initializer="zeros",
        bias_initializer=bias,
        activity_regularizer=reg,
    )(x)
    feat_T = layers.Reshape((num_features, num_features))(x)
    # Apply affine transformation to input features
    return layers.Dot(axes=(2, 1))([inputs, feat_T])
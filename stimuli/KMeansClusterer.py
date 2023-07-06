from labplatform.config import get_config
import os
import slab
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from matplotlib import pyplot as plt
from kneed import KneeLocator
import pathlib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from stimuli.features import zcr
import seaborn as sns
plt.rcParams['image.cmap'] = 'viridis'


class KMeansClusterer:
    """
    Class for signal selection based on maximum spectral differences. First, we calculate the Mel-frequency-cepstrum-
    coefficients (MFCCs) to label the input sound files based on spectral composition. The MFCCs serve as input for
    k-means clustering. Based on the clusters, we can select one talker in each group.
    MFCC works as follows:
    1. apply FT to time-sliced audio signal (usually 25 ms windows) --> compute spectrogram
    2. apply triangular filter bank on spectrogram --> mel-spectrogram (smoothened)
    3. calculate logarithm of the mel-spectrogram
    4. apply DCT to the output
    """
    def __init__(self, wavfile):
        self.wavfile = wavfile


if __name__ == "__main__":
    # kwargs important for kmeans clustering
    kmeans_kwargs = {"init": "kmeans++",
                     "n_init": 10,
                     "random_state": 42}

    # load and sort sound files by talker
    sound_type = "tts-countries_resamp_24414"
    sound_root = pathlib.Path("C:\labplatform\sound_files")
    sound_fp = pathlib.Path(os.path.join(sound_root, sound_type))
    sound_list = slab.Precomputed(slab.Sound.read(pathlib.Path(sound_fp / file)) for file in os.listdir(sound_fp))
    all_talkers = dict()
    talker_id_range = range(225, 377)
    for talker_id in talker_id_range:
        talker_sorted = list()
        for i, sound in enumerate(os.listdir(sound_fp)):
            if str(talker_id) in sound:
                talker_sorted.append(sound_list[i])
        all_talkers[str(talker_id)] = talker_sorted

    netto_talkers = dict()

    centroids = list()
    rolloffs = list()
    f0s = list()
    zcrs = list()

    for k, v in all_talkers.items():
        if all_talkers[k].__len__():
            netto_talkers[k] = k
            talker = all_talkers[k]
            centroids.append(np.mean([x.spectral_feature("centroid") for x in talker]))
            rolloffs.append(np.mean([x.spectral_feature("rolloff") for x in talker]))
            zcrs.append(np.mean([zcr(x.data) for x in talker]))
        else:
            continue

    centroids = np.reshape(centroids, (-1, 1))
    rolloffs = np.reshape(rolloffs, (-1, 1))
    zcrs = np.reshape(zcrs, (-1, 1))

    scaler = StandardScaler()  # basically z-score standardization
    scaled_centroids = np.array(np.round(scaler.fit_transform(centroids), 2))
    scaled_rolloffs = np.array(np.round(scaler.fit_transform(rolloffs), 2))
    scaled_zcrs = np.array(np.round(scaler.fit_transform(zcrs), 2))

    # put features together
    X = pd.DataFrame({"centroids": scaled_centroids.reshape(1, -1)[0],
                      "rolloffs": scaled_rolloffs.reshape(1, -1)[0],
                      "zrcs": scaled_zcrs.reshape(1, -1)[0]
                      })

    # PCA
    pca = PCA(2)
    data = pca.fit_transform(X)
    pca1 = [x[0] for x in data]
    pca2 = [x[1] for x in data]
    pcaX = pd.DataFrame({"pca1": pca1,
                         "pca2": pca2})

    # plot features
    plt.scatter(pcaX.pca1, pcaX.pca2)

    # do kmeans clustering and get elbow point
    sse = list()
    for cluster in range(1, 11):
        kmeans = KMeans(n_clusters=cluster, **kmeans_kwargs)
        kmeans.fit(data)
        sse.append(kmeans.inertia_)

    # plot sse
    plt.plot(range(1, 11), sse)
    plt.xticks(range(1, 11))
    plt.xlabel("Number of Clusters")
    plt.ylabel("SSE")
    plt.show()

    kl = KneeLocator(range(1, 11), sse, curve="convex", direction="decreasing")
    nclust_opt = 8  # seems 3 clusters is optimal

    # plot clusters in a scatter plot
    kmeans = KMeans(n_clusters=nclust_opt, **kmeans_kwargs)
    label = kmeans.fit_predict(data)
    pcaX["clusters"] = kmeans.labels_
    centroids = kmeans.cluster_centers_
    pcaX["talker"] = netto_talkers.keys()
    u_labels = np.unique(kmeans.labels_)

    for i in u_labels:
        plt.scatter(data[label == i, 0], data[label == i, 1], label=i)
    plt.scatter(centroids[:, 0], centroids[:, 1], s=80, marker="x", c="black")
    plt.legend()
    plt.colorbar()
    plt.show()

# 08 Rapporteringstakt per kommun

Källa: Valkolls publicerade kommuntabell (290 kommuner), hämtad från valkoll.com/incidentrapporter.

## 1. Reproduktion av publicerade tal

| figure                          |      published | reproduced     | match   |
|:--------------------------------|---------------:|:---------------|:--------|
| Reports with kommun             | 5077           | 5077           | True    |
| Eligible voters                 |    8.05136e+06 | 8051355        | True    |
| National rate per 10k           |    6.31        | 6.31           | True    |
| Kommuner without report         |   27           | 27             | True    |
| Highest rate (Munkfors)         |   78.33        | Munkfors 78.33 | True    |
| Lowest large (Västerås)         |    0.25        | Västerås 0.25  | True    |
| Kommuner with rate in [0, 2.5)  |   53           | 53             | True    |
| Kommuner with rate in [2.5, 5)  |   64           | 64             | True    |
| Kommuner with rate in [5, 10)   |   64           | 64             | True    |
| Kommuner with rate in [10, 20)  |   55           | 55             | True    |
| Kommuner with rate in [20, inf) |   27           | 27             | True    |

## 2. Är spridningen större än slumpen?

- Pearson-dispersion under gemensam rikstakt: 22.96 (1 vid ren Poisson), chi2 = 6637 på 289 fg, p = 0.0e+00.
- Utanför 95.0%-gränsen: 78 över, 71 under (väntat av slumpen: cirka 14.5).
- Utanför 99.8%-gränsen: 48 över, 43 under (väntat av slumpen: cirka 0.6).
- Negativ binomial, alfa = 1.035 (95 % KI 0.854 till 1.217); LR mot Poisson = 3791, p = 0.0e+00.
- Det motsvarar en variationskoefficient mellan kommuner på cirka 102% i den underliggande takten.

## 3. Beror takten på kommunens storlek?

- Elasticitet för takt mot röstberättigade: -0.237 (95 % KI -0.355 till -0.119, p = 8.0e-05). Negativt värde: större kommuner rapporterar färre per röstberättigad.
- AIC utan storlek 2084.9, med storlek 2072.6.

|                |   kommuner |   rapporter |   rostberattigade |   utan_rapport |   per_10k |
|:---------------|-----------:|------------:|------------------:|---------------:|----------:|
| 1 786–6 876    |         58 |         274 |  264033           |             11 |     10.38 |
| 6 876–10 050   |         58 |         498 |  487822           |              7 |     10.21 |
| 10 050–17 015  |         58 |         716 |  743363           |              6 |      9.63 |
| 17 015–35 147  |         58 |         901 |       1.4011e+06  |              2 |      6.43 |
| 35 147–765 741 |         58 |        2688 |       5.15504e+06 |              1 |      5.21 |

## 4. Shrinkage-skattningar (empirisk Bayes, gamma-Poisson)

- 162 av 290 kommuner har ett 95 %-intervall som inte omfattar rikstakten 6.31.

Högst efter shrinkage:

| namn       |   rapporter |   rostberattigade |   raw_per_10k |   raw_rank |   eb_per_10k |   eb_lo95 |   eb_hi95 |   eb_rank |
|:-----------|------------:|------------------:|--------------:|-----------:|-------------:|----------:|----------:|----------:|
| Munkfors   |          21 |              2681 |         78.33 |          1 |        52.14 |     32.67 |     76.11 |         1 |
| Bollebygd  |          42 |              7432 |         56.51 |          2 |        47.93 |     34.69 |     63.29 |         2 |
| Torsby     |          46 |              8619 |         53.37 |          3 |        46.27 |     33.99 |     60.41 |         3 |
| Knivsta    |          76 |             15318 |         49.61 |          5 |        45.68 |     36.05 |     56.43 |         4 |
| Herrljunga |          37 |              7356 |         50.3  |          4 |        42.72 |     30.22 |     57.34 |         5 |
| Mönsterås  |          48 |             10110 |         47.48 |          7 |        42.06 |     31.11 |     54.63 |         6 |
| Orust      |          54 |             12459 |         43.34 |          8 |        39.29 |     29.59 |     50.33 |         7 |
| Ockelbo    |          22 |              4611 |         47.71 |          6 |        37.39 |     23.69 |     54.16 |         8 |
| Burlöv     |          46 |             14158 |         32.49 |         12 |        29.93 |     21.99 |     39.08 |         9 |
| Storuman   |          16 |              4421 |         36.19 |          9 |        28.5  |     16.59 |     43.58 |        10 |

Lägst efter shrinkage:

| namn        |   rapporter |   rostberattigade |   raw_per_10k |   raw_rank |   eb_per_10k |   eb_lo95 |   eb_hi95 |   eb_rank |
|:------------|------------:|------------------:|--------------:|-----------:|-------------:|----------:|----------:|----------:|
| Trosa       |           0 |             11406 |          0    |        264 |         0.75 |      0.02 |      2.8  |       281 |
| Söderköping |           0 |             11471 |          0    |        264 |         0.74 |      0.02 |      2.78 |       282 |
| Hedemora    |           0 |             11836 |          0    |        264 |         0.72 |      0.02 |      2.71 |       283 |
| Vimmerby    |           0 |             11955 |          0    |        264 |         0.72 |      0.02 |      2.68 |       284 |
| Partille    |           1 |             29898 |          0.33 |        261 |         0.63 |      0.07 |      1.75 |       285 |
| Gislaved    |           0 |             21356 |          0    |        264 |         0.42 |      0.01 |      1.58 |       286 |
| Höganäs     |           0 |             22109 |          0    |        264 |         0.41 |      0.01 |      1.53 |       287 |
| Gotland     |           1 |             48457 |          0.21 |        263 |         0.39 |      0.05 |      1.1  |       288 |
| Västerås    |           3 |            121802 |          0.25 |        262 |         0.32 |      0.09 |      0.71 |       289 |
| Borlänge    |           0 |             39713 |          0    |        264 |         0.23 |      0.01 |      0.88 |       290 |

Största kommunerna utan rapport:

| namn        |   rapporter |   rostberattigade |   raw_per_10k |   raw_rank |   eb_per_10k |   eb_lo95 |   eb_hi95 |   eb_rank |
|:------------|------------:|------------------:|--------------:|-----------:|-------------:|----------:|----------:|----------:|
| Borlänge    |           0 |             39713 |             0 |        264 |         0.23 |      0.01 |      0.88 |       290 |
| Höganäs     |           0 |             22109 |             0 |        264 |         0.41 |      0.01 |      1.53 |       287 |
| Gislaved    |           0 |             21356 |             0 |        264 |         0.42 |      0.01 |      1.58 |       286 |
| Vimmerby    |           0 |             11955 |             0 |        264 |         0.72 |      0.02 |      2.68 |       284 |
| Hedemora    |           0 |             11836 |             0 |        264 |         0.72 |      0.02 |      2.71 |       283 |
| Söderköping |           0 |             11471 |             0 |        264 |         0.74 |      0.02 |      2.78 |       282 |
| Trosa       |           0 |             11406 |             0 |        264 |         0.75 |      0.02 |      2.8  |       281 |
| Lysekil     |           0 |             11182 |             0 |        264 |         0.76 |      0.02 |      2.84 |       280 |

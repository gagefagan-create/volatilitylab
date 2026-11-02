# Synthetic fixture

`synthetic_prices.csv` is not market data. It contains 300 artificial business-day prices generated from independent Gaussian log returns (standard deviation .012, zero mean), seed 1729, and initial scale 100. It exercises alignment and leakage checks offline. The Yahoo-shaped temporary cache in the calendar test is also entirely synthetic.

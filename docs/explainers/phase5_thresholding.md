# Phase 5 Explainer: Statistical Thresholding

## 1. Concepts & Architecture
To prevent the fraud detector from being artificially tuned to always find the planted ring (which would make the demonstration look rigged and lose credibility under judge questioning), we implement **Statistical Thresholding**.

### The Fairness Rule: Threshold Freezing
The core of this methodology is to calculate the thresholds on the **real background data distribution first**, before any synthetic anomalies or fraud rings are introduced.

```text
  [REAL BACKGROUND DATA] 
            │
            ▼
  [Calculate Mean (μ) and Std Dev (σ)] 
            │
            ▼
  [Freeze Thresholds: (μ + 2*σ)] <─── Thresholds are locked here!
            │
            ▼
  [Inject Synthetic Fraud Ring] 
            │
            ▼
  [Run Detection Engine]
```

### The Math: $z$-Score
We calculate the $z$-score for the numerical signals (like address degree and director degree) of any company to see how many standard deviations away it is from the typical company in the population.

- **Formula**:
  $$z = \frac{x - \mu}{\sigma}$$
  Where:
  - $x$ is the company's raw feature value (e.g., Director Degree = 8).
  - $\mu$ is the mean of that feature across the background dataset.
  - $\sigma$ is the standard deviation of that feature across the background dataset.

- **Threshold Level**: We set the anomaly threshold at $z \ge 2.0$ (representing the top ~2.5% of the tail in a standard normal distribution).

---

## 2. Phase 5 Self-Assessment Quiz

### Question 1:
Why must we calculate and freeze statistical thresholds using the real background data *before* planting the synthetic fraud ring?
<details>
<summary><b>Show Answer</b></summary>
If we set thresholds <i>after</i> adding the fraud ring, we could easily hard-code or fine-tune the numbers (e.g., setting the director threshold to exactly the number of companies in our fraud ring) to guarantee a 100% detection rate. Freezing the thresholds on the background data first ensures the system is evaluated honestly, proving it discovers the anomaly based on its statistical variance rather than manual tuning.
</details>

### Question 2:
What does a $z$-score of $+3.0$ on director degree mean, and how does it translate to risk?
<details>
<summary><b>Show Answer</b></summary>
A $z$-score of $+3.0$ means the director is connected to a number of companies that is 3 standard deviations above the average director in the background population. This represents a highly unusual statistical outlier, mapping to a high risk score for that specific signal.
</details>

### Question 3:
If the background data's mean address degree is 1.2 and the standard deviation is 0.5, what is the threshold for a $z$-score of 2.0?
<details>
<summary><b>Show Answer</b></summary>
The threshold is:
$$\text{Threshold} = \mu + 2\sigma = 1.2 + 2(0.5) = 2.2$$
Therefore, any address with 3 or more companies registered (since company count must be an integer) will exceed the $z$-score threshold of 2.0.
</details>

# Phase 6 Explainer: Composite Likelihood Scoring

## 1. Concepts & Architecture
The system converts raw graph and entity measurements into normalized risk scores between 0 and 100, which are then combined into a single **Shell Likelihood / Network Risk screening score** (0 to 100).

---

### Signal Normalization Mapping
To combine different features (degrees, dates, currency amounts), we normalize each raw value to a 0–100 scale:

1. **Address Clustering Risk ($S_A$)**:
   - If raw address degree is $\le \mu_{\text{addr}} + z_{\text{thresh}}\sigma_{\text{addr}}$, risk is 0.
   - If it exceeds the threshold, it scales up to 100 as the degree increases (e.g., reaching 100 at 15 companies).

2. **Director Degree Risk ($S_B$)**:
   - If max director degree is $\le \mu_{\text{dir}} + z_{\text{thresh}}\sigma_{\text{dir}}$, risk is 0.
   - Otherwise, scales linearly to 100 (reaching 100 at 8 companies, which is a common statutory/practical limit).

3. **Incorporation Burst Risk ($S_C$)**:
   - Scales with the number of related companies registered within the date window.
   - E.g., 1 company = 0 risk, 2 companies = 20, 3 companies = 50, $\ge 5$ companies = 100 risk.

4. **Capital & Filing Mismatch Risk ($S_D$)**:
   - Risk is composite of:
     - **50 points** if the company status is a filing defaulter or has nil filings.
     - **50 points** if the paid-up capital is zero or less than 1% of the authorized capital.

---

### Weighted Composite Formula
The individual normalized signals are combined using a weighted average:

$$\text{Composite Score} = w_A S_A + w_B S_B + w_C S_C + w_D S_D$$

- **Default Weights**: 25% each ($w_A = w_B = w_C = w_D = 0.25$).
- **Configurability**: Weights are loaded from environment variables (`.env`) to allow investigators to adjust the model's sensitivity.

---

## 2. Phase 6 Self-Assessment Quiz

### Question 1:
Why is it better to call the final metric "Shell Likelihood / Network Risk screening score" rather than "probability of fraud"?
<details>
<summary><b>Show Answer</b></summary>
"Probability of fraud" implies a definitive, mathematically proven likelihood of criminal activity, which requires legal and factual evidence that cannot be inferred solely from relationship filings. Framing it as a "Screening Score" or "Likelihood" correctly positions the system as a <i>decision-support tool</i> for human investigators to prioritize cases, avoiding false accusations and maintaining regulatory compliance.
</details>

### Question 2:
How do we prevent a company with a high capital and active filing history from being ranked as high-risk, even if it shares a registered CA office address?
<details>
<summary><b>Show Answer</b></summary>
Because the final score is a <b>weighted average</b>. If a company shares a CA office (high Address Risk, e.g. 80/100) but has normal director associations (Director Risk = 0), is registered years apart from neighbors (Burst Risk = 0), and has active filings with high paid-up capital (Capital Risk = 0), the weighted composite score will be:
$$\text{Score} = 0.25(80) + 0.25(0) + 0.25(0) + 0.25(0) = 20/100$$
This is a low-risk rating, effectively filtering out the false positive.
</details>

### Question 3:
How can an investigator customize the scoring weights for a campaign specifically targeting new "fly-by-night" operators?
<details>
<summary><b>Show Answer</b></summary>
They can adjust the weights in the environment configuration (<code>.env</code>). For new fly-by-night operators, they would increase the weight of the <b>Incorporation Burst Signal</b> (e.g., 40%) and <b>Filing Mismatch Signal</b> (e.g., 40%) while reducing the weight of address sharing (e.g., 10%) and director degree (e.g., 10%).
</details>

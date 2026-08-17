export default function Page() {
  return (
    <section className="view active">
          <div className="layout" style={{ gridTemplateColumns: "1fr" }}>
            <div>
              <div className="metrics" style={{ maxWidth: 1150 }}>
                <div className="metric lead"><div className="v num">0.681</div>
                  <div className="k">Flood IoU — learned</div></div>
                <div className="metric"><div className="v num">0.550</div>
                  <div className="k">Flood IoU — threshold</div></div>
                <div className="metric"><div className="v num">0.822</div>
                  <div className="k">Precision</div></div>
                <div className="metric"><div className="v num">0.016</div>
                  <div className="k">Calibration error</div></div>
                <div className="metric"><div className="v num">446</div>
                  <div className="k">Benchmark chips</div></div>
              </div>
              <div className="card" style={{ maxWidth: 1150 }}>
                <h3>Method</h3>
                <div className="note" style={{ fontSize: 13 }}>
                  <p style={{ marginBottom: 11 }}>
                    <b>SAR</b> satellites fire radar pulses and measure the echo, so they
                    work at night and through cloud — the only sensor that keeps working
                    through the Indian monsoon. The output is a grayscale map of surface
                    texture, not a photograph, and reading it takes years of training.
                  </p>
                  <p style={{ marginBottom: 11 }}>
                    Figures above are the Sen1Floods11 <b>official test split</b> at 512 px,
                    ResNet34 encoder with ImageNet weights. The threshold baseline uses
                    dual polarisation (VV &lt; −18.5 dB OR VH &lt; −24 dB), tuned on
                    validation only. Train/validation splits are by <b>scene</b>, not
                    patch — adjacent tiles of one place on both sides would inflate the
                    score.
                  </p>
                  <p style={{ marginBottom: 11 }}>
                    Probabilities are temperature-calibrated (T = 1.368), reducing expected
                    calibration error from 0.029 to <b>0.016</b> with IoU unchanged.
                  </p>
                  <p>
                    <b>Colorization is the weaker half.</b> It beats a constant-mean
                    baseline (15.01 vs 13.52 dB) and carries genuine scene-specific signal
                    — SSIM halves when outputs are paired with the wrong ground truth — but
                    its colour saturation is 26% of reality and its spatial variance 10%.
                    The confidence map exists to make that visible rather than hidden.
                  </p>
                </div>
              </div>
            </div>
          </div>
    </section>
  );
}

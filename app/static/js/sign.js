// Contents moved from sign.html's <script> block to this file

const token = window.config.token;
const clientName = window.config.client_name;

document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("signature-pad");
    const signaturePad = new window.SignaturePad(canvas);

    function resizeCanvas() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const data = signaturePad.toData();
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
        signaturePad.clear();
        signaturePad.fromData(data);
    }

    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    document.getElementById("clear-btn").addEventListener("click", () => {
        signaturePad.clear();
    });

    document.getElementById("submit-btn").addEventListener("click", () => {
        const consentChecked = document.getElementById("consent").checked;

        if (!consentChecked) {
            alert("You must agree to the terms before signing.");
            return;
        }

        if (signaturePad.isEmpty()) {
            alert("Please provide a signature.");
            return;
        }

        const signatureData = signaturePad.toDataURL();

        fetch(`/api/v1/sign/${token}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                signature: signatureData,
                consent: true
            })
        })
            .then(response => {
                if (!response.ok) throw new Error("Signing failed.");
                return response.json();
            })
            .then(data => {
                alert("Signature submitted successfully.");
                window.location.href = "/v1/thank-you";
            })
            .catch(err => {
                console.error(err);
                alert("Error submitting signature.");
            });
    });
});

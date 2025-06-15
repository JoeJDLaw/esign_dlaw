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
        const submitBtn = document.getElementById("submit-btn");
        const clearBtn = document.getElementById("clear-btn");
        const consentChecked = document.getElementById("consent").checked;
        const loadingMsg = document.getElementById("loading-msg");
        const loadingOverlay = document.getElementById("loadingOverlay");
        const pageContent = document.body;

        if (!consentChecked) {
            alert("You must agree to the terms before signing.");
            return;
        }

        if (signaturePad.isEmpty()) {
            alert("Please provide a signature.");
            return;
        }

        const signatureData = signaturePad.toDataURL();

        // Show enhanced loading state
        showLoadingState(submitBtn, clearBtn, loadingMsg, loadingOverlay, pageContent);

        fetch(`/v1/sign/${token}`, {
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
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || "Signing failed.");
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    throw new Error("No redirect URL provided.");
                }
            })
            .catch(err => {
                console.error(err);
                alert(err.message || "Error submitting signature.");
                // Re-enable everything on error
                hideLoadingState(submitBtn, clearBtn, loadingMsg, loadingOverlay, pageContent);
            });
    });

    function showLoadingState(submitBtn, clearBtn, loadingMsg, loadingOverlay, pageContent) {
        // Disable all interactive elements
        submitBtn.disabled = true;
        clearBtn.disabled = true;
        
        // Disable signature pad
        signaturePad.off();
        
        // Show loading overlay
        if (loadingOverlay) {
            loadingOverlay.style.display = "block";
        }
        
        // Show old loading message as fallback
        if (loadingMsg) {
            loadingMsg.style.display = "block";
        }
        
        // Prevent body scrolling
        document.body.style.overflow = "hidden";
    }

    function hideLoadingState(submitBtn, clearBtn, loadingMsg, loadingOverlay, pageContent) {
        // Re-enable interactive elements
        submitBtn.disabled = false;
        clearBtn.disabled = false;
        
        // Re-enable signature pad
        signaturePad.on();
        
        // Hide loading overlay
        if (loadingOverlay) {
            loadingOverlay.style.display = "none";
        }
        
        // Hide loading message
        if (loadingMsg) {
            loadingMsg.style.display = "none";
        }
        
        // Restore body scrolling
        document.body.style.overflow = "auto";
    }
});

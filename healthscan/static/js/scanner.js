// Barcode Scanner Controller using html5-qrcode
document.addEventListener('DOMContentLoaded', () => {
  const btnToggleCamera = document.getElementById('btn-toggle-camera');
  const manualScanForm = document.getElementById('manual-scan-form');
  const manualBarcode = document.getElementById('manual-barcode');
  const errorMessage = document.getElementById('error-message');
  const scanLoading = document.getElementById('scan-loading');
  const loadingBarcodeLabel = document.getElementById('loading-barcode-label');
  const laser = document.getElementById('laser');

  let html5Qrcode = null;
  let isScanning = false;

  // Initialize Html5Qrcode instance
  if (document.getElementById('reader')) {
    html5Qrcode = new Html5Qrcode("reader");
  }

  // Toggle Camera
  btnToggleCamera.addEventListener('click', async () => {
    if (!html5Qrcode) return;

    if (isScanning) {
      await stopCamera();
    } else {
      await startCamera();
    }
  });

  async function startCamera() {
    errorMessage.style.display = 'none';
    try {
      // Show scanning visual helper
      laser.style.display = 'block';
      
      const config = {
        fps: 15,
        qrbox: (width, height) => {
          // Landscape box optimized for 1D barcodes
          const boxWidth = Math.min(width * 0.8, 320);
          const boxHeight = Math.min(height * 0.4, 150);
          return { width: boxWidth, height: boxHeight };
        },
        formatsToSupport: [ 
          Html5QrcodeSupportedFormats.EAN_13, 
          Html5QrcodeSupportedFormats.EAN_8, 
          Html5QrcodeSupportedFormats.UPC_A, 
          Html5QrcodeSupportedFormats.UPC_E,
          Html5QrcodeSupportedFormats.CODE_128
        ]
      };

      await html5Qrcode.start(
        { facingMode: "environment" },
        config,
        onScanSuccess,
        onScanError
      );

      isScanning = true;
      btnToggleCamera.innerHTML = `<i class="fa-solid fa-stop me-1"></i> <span data-translate="btn_stop_camera">Stop Camera</span>`;
      // Run translation helper in case language was switched
      if (typeof translatePage === 'function') translatePage(PREFERRED_LANGUAGE);

    } catch (err) {
      console.error("Camera start failed:", err);
      errorMessage.textContent = "Camera access denied or device not found.";
      errorMessage.style.display = 'block';
      laser.style.display = 'none';
    }
  }

  async function stopCamera() {
    if (!html5Qrcode || !isScanning) return;
    try {
      await html5Qrcode.stop();
      isScanning = false;
      laser.style.display = 'none';
      btnToggleCamera.innerHTML = `<i class="fa-solid fa-camera me-1"></i> <span data-translate="btn_start_camera">Start Camera</span>`;
      if (typeof translatePage === 'function') translatePage(PREFERRED_LANGUAGE);
    } catch (err) {
      console.error("Camera stop failed:", err);
    }
  }

  function onScanSuccess(decodedText, decodedResult) {
    console.log(`Scan result: ${decodedText}`, decodedResult);
    // Vibrate device if supported
    if (navigator.vibrate) {
      navigator.vibrate(100);
    }
    // Stop camera and process
    stopCamera().then(() => {
      submitBarcode(decodedText);
    });
  }

  function onScanError(errorMessage) {
    // Repeated scans of blank spaces report errors. Quiet log.
  }

  // Handle manual input form
  manualScanForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const barcode = manualBarcode.value.trim();
    if (!/^\d+$/.test(barcode)) {
      errorMessage.textContent = "Please enter a valid numeric barcode.";
      errorMessage.style.display = 'block';
      return;
    }
    submitBarcode(barcode);
  });

  // AJAX barcode submission to Django REST API
  function submitBarcode(barcode) {
    errorMessage.style.display = 'none';
    scanLoading.style.display = 'block';
    loadingBarcodeLabel.textContent = `Barcode: ${barcode}`;

    // Get CSRF Token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch('/api/scan/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ barcode: barcode })
    })
    .then(response => {
      if (!response.ok) {
        return response.json().then(err => { throw err; });
      }
      return response.json();
    })
    .then(data => {
      // Success: Redirect to Results Page
      window.location.href = `/results/${barcode}/`;
    })
    .catch(error => {
      console.error("Scan submission error:", error);
      scanLoading.style.display = 'none';
      errorMessage.textContent = error.error || "An error occurred during analysis. Try again.";
      errorMessage.style.display = 'block';
    });
  }
});

document.addEventListener('DOMContentLoaded', function () {
    const startCameraButton = document.getElementById('start-camera');
    const qrCodeReaderDiv = document.getElementById('reader');
    let html5QrCode;

    startCameraButton.addEventListener('click', () => {
        qrCodeReaderDiv.style.display = 'block';
        html5QrCode = new Html5Qrcode("reader");
        html5QrCode.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, onScanSuccess, onScanFailure)
            .catch((err) => {
                console.error(`Unable to start QR scanner: ${err}`);
            });
    });

    function onScanSuccess(decodedText, decodedResult) {
        console.log(`Code scanned = ${decodedText}`, decodedResult);
        handleQRCodeScanned(decodedText);
        fetch('/qr_scan', {
            method: 'POST',
            body: JSON.stringify({}),
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            // Handle response if needed
        })
        .catch(error => {
            // Handle error if any
        });
    }

    function onScanFailure(error) {
        console.warn(`Code scan error = ${error}`);
    }

    function handleQRCodeScanned(decodedText) {
        // Parse the decodedText into a JSON object
        const keyValuePairs = decodedText.split(',');
        const qrCodeData = keyValuePairs.reduce((acc, current) => {
            const [key, value] = current.split(':');
            acc[key.trim()] = value.trim();
            return acc;
        }, {});

        console.log(`QR Code Data:`, qrCodeData); // Log to verify the structure

        // Extracting latitude and longitude from qrCodeData
        const teacherLatitude = parseFloat(qrCodeData.Latitude);
        const teacherLongitude = parseFloat(qrCodeData.Longitude);

        navigator.geolocation.getCurrentPosition(function (position) {
            const studentLatitude = position.coords.latitude;
            const studentLongitude = position.coords.longitude;
            console.log(`Student's location: Latitude = ${studentLatitude}, Longitude = ${studentLongitude}`);

            const distance = calculateDistance(teacherLatitude, teacherLongitude, studentLatitude, studentLongitude);
            console.log(`Calculated distance: ${distance} meters`);

            const allowedRadius = 0.1 * 1000; // Convert to meters
            if (!isNaN(distance) && distance <= allowedRadius) {
                stopCamera();
                alert("You are within the allowed radius. Marking attendance.");
                markAttendance(qrCodeData);
            } else {
                stopCamera();
                alert("You are not within the allowed radius to mark attendance.");
            }
            stopCamera();
        }, function (error) {
            alert(`Error getting location: ${error.message}`);
            stopCamera();
        });
    }

    function markAttendance(qrCodeData) {
        fetch('/mark_attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ qr_code_data: qrCodeData }),
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                alert(data.message);
            })
            .catch((error) => {
                console.error('Error:', error);
                alert(`Failed to mark attendance: ${error.message}`);
            });
    }

    function stopCamera() {
        if (html5QrCode) {
            html5QrCode.stop().then(() => {
                qrCodeReaderDiv.style.display = 'none';
                console.log("QR Scanner stopped.");
            }).catch((err) => {
                console.error("Failed to stop the QR scanner", err);
            });
        }
    }

    function calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Radius of the Earth in kilometers
        const dLat = toRad(lat2 - lat1);
        const dLon = toRad(lon2 - lon1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        const d = R * c;
        return d * 1000; // Convert to meters
    }
    
    function toRad(x) {
        return x * Math.PI / 180;
    }
    
});
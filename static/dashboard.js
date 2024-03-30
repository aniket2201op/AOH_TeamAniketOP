document.getElementById('generateQR').addEventListener('click', function (event) {
    event.preventDefault(); // Prevent the default form submission behavior
    navigator.geolocation.getCurrentPosition(function (position) {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;
        const subject = document.getElementById('subject').value;
        const currentDate = new Date().toISOString().slice(0, 10);
        const duration = document.getElementById('duration').value;
        const user_id = document.getElementById('userid').value;
        // Get current date in YYYY-MM-DD format
        const qrData = { user_id: user_id, subject: subject, date: currentDate, latitude: latitude, longitude: longitude };

        fetch('/generate_qr_with_location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', },
            body: JSON.stringify(qrData),
        })
            .then(response => response.blob())
            .then(data => {
                const url = URL.createObjectURL(data);
                document.getElementById('overlay-qrcode').innerHTML = `<img src="${url}" alt="QR Code">`;
                document.getElementById('overlay').style.display = 'block';
                document.getElementById('overlay-subject').textContent = `Subject: ${subject}`;
                document.getElementById('overlay-date').textContent = `Date: ${currentDate}`;
                startCountdown(duration);
            })
            .catch(error => console.error('Error generating QR code:', error));
    }, function (error) {
        alert("Error obtaining location. Please allow location access.");
    });
});

document.getElementById('closeOverlay').addEventListener('click', function () {
    document.getElementById('overlay').style.display = 'none';
    clearInterval(countdownTimer); // Stop the countdown timer
    rejectAttendance(); // Call the rejectAttendance function
});

function rejectAttendance() {
    // Fetch user_id from HTML content
    const subject = document.getElementById('subject').value;
    // console.log("Subject is" + subject)
    fetch('/reject_attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: subject })
    })
        .then(response => {
            if (!response.ok) {
                // Handle success response if needed
                console.log('Attendance could not reject.');
            } 
        })
        .catch(error => {
            // Handle fetch error
            console.error('Error rejecting attendance:', error);
        });
}
function displayPresentRollNumbers(presentRollNumbers) {
    const overlay = document.createElement('div');
    overlay.className = 'overlay1';
    const overlayContent = document.createElement('div');
    overlayContent.className = 'overlay1-content';  
    if (presentRollNumbers.length > 0) {
        const rollNumbersHeader = document.createElement('h2');
        rollNumbersHeader.textContent = 'Present Roll Numbers:';
        const rollNumbersList = document.createElement('ul');

        presentRollNumbers.forEach(rollNumber => {
            const listItem = document.createElement('li');
            listItem.textContent = rollNumber;
            rollNumbersList.appendChild(listItem);
        });

        overlayContent.appendChild(rollNumbersHeader);
        overlayContent.appendChild(rollNumbersList);
    } else {
        const errorMessage = document.createElement('p');
        errorMessage.textContent = 'No present roll numbers found.';
        overlayContent.appendChild(errorMessage);
    }

    const closeButton = document.createElement('button');
    closeButton.textContent = 'Close';
    closeButton.addEventListener('click', function () {
        document.body.removeChild(overlay);
    });

    overlayContent.appendChild(closeButton);
    overlay.appendChild(overlayContent);
    document.body.appendChild(overlay);
}


function startCountdown(durationInMinutes) {
    let durationInSeconds = durationInMinutes * 60;
    const countdownElement = document.getElementById('countdown');
    const countdownTimer = setInterval(function () {
        durationInSeconds--;
        const minutes = Math.floor(durationInSeconds / 60);
        const seconds = durationInSeconds % 60;
        countdownElement.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
        if (durationInSeconds <= 0) {
            clearInterval(countdownTimer);
            document.getElementById('overlay').style.display = 'none';
            rejectAttendance(); // Call the rejectAttendance function
            const subject = document.getElementById('subject').value;

            // Make a POST request to fetch present roll numbers for the selected subject
            fetch('/get_present_roll_numbers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subject: subject })
            })
                .then(response => response.json())
                .then(data => {
                    displayPresentRollNumbers(data.present_values);
                })
                .catch(error => {
                    alert("Can not fetch the Present Numbers or Attendance is not marked.");
                });
        }
    }, 1000);
}

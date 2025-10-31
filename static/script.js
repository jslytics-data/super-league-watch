document.addEventListener('DOMContentLoaded', function() {
    const matchesContainer = document.getElementById('matches-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const errorMessage = document.getElementById('error-message');
    const lastUpdatedElement = document.getElementById('last-updated');
    const mainTitleElement = document.getElementById('main-title');

    const REFRESH_INTERVAL_SECONDS = 30;

    function renderMatches(data) {
        if (!data || !data.matches) {
            showError('Invalid data received from the server.');
            return;
        }
        
        mainTitleElement.textContent = `Super League Watch - Round ${data.round_id}`;
        
        const table = document.createElement('table');
        table.className = 'match-table';
        
        const header = table.createTHead();
        const headerRow = header.insertRow();
        headerRow.innerHTML = '<th>Home</th><th>Score</th><th>Away</th><th>Status</th>';
        
        const tbody = table.createTBody();
        data.matches.forEach(match => {
            const row = tbody.insertRow();
            
            const homeTeamCell = row.insertCell();
            homeTeamCell.className = 'team-name';
            homeTeamCell.textContent = match.home_team;
            
            const scoreCell = row.insertCell();
            scoreCell.className = 'score';
            scoreCell.textContent = match.score || '-';
            
            const awayTeamCell = row.insertCell();
            awayTeamCell.className = 'team-name';
            awayTeamCell.textContent = match.away_team;
            
            const statusCell = row.insertCell();
            const statusDiv = document.createElement('div');
            statusDiv.className = `status status-${match.status}`;
            statusDiv.textContent = match.status.replace('_', ' ');
            statusCell.appendChild(statusDiv);

            if (match.live_minute) {
                const minuteDiv = document.createElement('div');
                minuteDiv.className = 'live-minute';
                minuteDiv.textContent = `${match.live_minute}'`;
                statusCell.appendChild(minuteDiv);
            }
        });
        
        matchesContainer.innerHTML = '';
        matchesContainer.appendChild(table);
    }

    function showLoading() {
        loadingSpinner.classList.remove('hidden');
        errorMessage.classList.add('hidden');
        matchesContainer.innerHTML = '';
    }

    function hideLoading() {
        loadingSpinner.classList.add('hidden');
    }

    function showError(message) {
        errorMessage.textContent = `Error: ${message}. Retrying in ${REFRESH_INTERVAL_SECONDS} seconds.`;
        errorMessage.classList.remove('hidden');
    }
    
    async function fetchData() {
        try {
            const response = await fetch('/api/get_current_round');
            if (!response.ok) {
                throw new Error(`Server responded with status ${response.status}`);
            }
            const data = await response.json();
            hideLoading();
            renderMatches(data);
            const now = new Date();
            lastUpdatedElement.textContent = `Last Updated: ${now.toLocaleTimeString()}`;
        } catch (error) {
            console.error('Failed to fetch match data:', error);
            hideLoading();
            showError(error.message);
        }
    }

    showLoading();
    fetchData();
    setInterval(fetchData, REFRESH_INTERVAL_SECONDS * 1000);
});
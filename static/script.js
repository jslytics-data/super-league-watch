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
        
        mainTitleElement.textContent = `${data.competition_name} - Round ${data.round_id}`;
        matchesContainer.innerHTML = ''; // Clear previous content

        data.matches.forEach(match => {
            const card = document.createElement('div');
            card.className = 'match-card';

            const homeTeam = document.createElement('div');
            homeTeam.className = 'team team-home';
            homeTeam.textContent = match.home_team;

            const score = document.createElement('div');
            score.className = 'score';
            score.textContent = match.score || '-';

            const awayTeam = document.createElement('div');
            awayTeam.className = 'team team-away';
            awayTeam.textContent = match.away_team;
            
            const statusInfo = document.createElement('div');
            statusInfo.className = 'status-info';

            if (match.status === 'not_started') {
                statusInfo.innerHTML = `<div>${match.date}</div><div>${match.kick_off_time_utc} (UTC)</div>`;
            } else if (match.status === 'in_play') {
                statusInfo.innerHTML = `<span class="live-indicator">LIVE</span><span class="live-minute">${match.live_minute}'</span>`;
            } else if (match.status === 'completed') {
                statusInfo.textContent = 'Full Time';
            }

            card.appendChild(homeTeam);
            card.appendChild(score);
            card.appendChild(awayTeam);
            card.appendChild(statusInfo);
            
            matchesContainer.appendChild(card);
        });
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
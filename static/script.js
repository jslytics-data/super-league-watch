document.addEventListener('DOMContentLoaded', function() {
    const matchesContainer = document.getElementById('matches-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const errorMessage = document.getElementById('error-message');
    const lastUpdatedElement = document.getElementById('last-updated');
    const mainTitleElement = document.getElementById('main-title');

    const REFRESH_INTERVAL_SECONDS = 30;

    function formatTime(utcDate, utcTime) {
        if (!utcDate || !utcTime) return '';
        
        if (String(utcTime).length <= 2) {
            utcTime += ':00';
        }

        const dateString = `${utcDate}T${utcTime}:00Z`;
        const date = new Date(dateString);

        if (isNaN(date)) return '';
        
        const options = {
            timeZone: 'Europe/Athens',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        };
        
        return new Intl.DateTimeFormat('el-GR', options).format(date);
    }

    function renderTeamCell(cell, match, teamType) {
        const teamName = match[`${teamType}_team`];
        const teamNameGreek = match[`${teamType}_team_greek`] || teamName;
        const subredditUrl = match[`${teamType}_team_subreddit`];
        
        cell.className = `team-${teamType}`;

        if (subredditUrl) {
            const link = document.createElement('a');
            link.href = subredditUrl;
            link.target = '_blank';
            link.textContent = teamNameGreek;
            cell.appendChild(link);
        } else {
            cell.textContent = teamNameGreek;
        }
    }

    function renderMatches(data) {
        if (!data || !data.matches) {
            showError('Invalid data received from the server.');
            return;
        }
        
        mainTitleElement.textContent = `${data.competition_name} - Round ${data.round_id}`;
        
        const tableContainer = document.createElement('div');
        tableContainer.className = 'table-container';

        const table = document.createElement('table');
        table.className = 'match-table';
        
        const header = table.createTHead();
        const headerRow = header.insertRow();
        headerRow.innerHTML = '<th>Home</th><th>Score</th><th>Away</th><th>Status</th>';
        
        const tbody = table.createTBody();
        data.matches.forEach(match => {
            const row = tbody.insertRow();
            
            renderTeamCell(row.insertCell(), match, 'home');
            
            const scoreCell = row.insertCell();
            scoreCell.className = 'score';
            scoreCell.textContent = match.score || '-';
            
            renderTeamCell(row.insertCell(), match, 'away');
            
            const statusCell = row.insertCell();
            statusCell.className = 'status-info';

            if (match.status === 'not_started') {
                const localTime = formatTime(match.date, match.kick_off_time_utc);
                statusCell.innerHTML = `<div>${match.date}</div><div>${localTime}</div>`;
            } else if (match.status === 'in_play') {
                statusCell.innerHTML = `<div><span class="live-indicator">LIVE</span></div><div>${match.live_minute}'</div>`;
            } else if (match.status === 'completed') {
                statusCell.textContent = 'Full Time';
            }
        });
        
        tableContainer.appendChild(table);
        matchesContainer.innerHTML = '';
        matchesContainer.appendChild(tableContainer);
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
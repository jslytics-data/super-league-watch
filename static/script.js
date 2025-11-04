document.addEventListener('DOMContentLoaded', function() {
    const API_ENDPOINT = '/api/get_current_round';
    const REFRESH_INTERVAL_MS = 30000;

    const mainTitle = document.getElementById('main-title');
    const roundInfo = document.getElementById('round-info');
    const lastUpdated = document.getElementById('last-updated');
    const matchesContainer = document.getElementById('matches-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const errorMessage = document.getElementById('error-message');

    let grTimezone;
    try {
        grTimezone = 'Europe/Athens';
        new Intl.DateTimeFormat('en-US', { timeZone: grTimezone }).format();
    } catch (e) {
        console.warn("Could not resolve Europe/Athens timezone, falling back to local.");
        grTimezone = new Intl.DateTimeFormat().resolvedOptions().timeZone;
    }
    
    function formatGreekTime(dateStr, timeStr) {
        if (!dateStr || !timeStr) return '';
        if (timeStr.length <= 2) timeStr += ':00';
        
        const utcDateTime = new Date(`${dateStr}T${timeStr}:00Z`);
        const dateOptions = { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: grTimezone };
        const timeOptions = { hour: '2-digit', minute: '2-digit', timeZone: grTimezone, hour12: false };
        
        const formattedDate = new Intl.DateTimeFormat('en-CA', dateOptions).format(utcDateTime);
        const formattedTime = new Intl.DateTimeFormat('en-GB', timeOptions).format(utcDateTime);
        
        return { date: formattedDate, time: formattedTime };
    }

    function renderTable(data) {
        const competitionName = data.competition_name || 'League';
        const roundId = data.round_id || 'Current Round';

        document.title = `${competitionName} Watch - ${roundId}`;
        mainTitle.textContent = `${competitionName} Watch`;
        roundInfo.textContent = roundId;

        if (data.last_updated_utc) {
            const updatedDate = new Date(data.last_updated_utc);
            const options = {
                hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: grTimezone
            };
            lastUpdated.textContent = `Last Updated: ${updatedDate.toLocaleTimeString('en-GB', options)} (GR)`;
        }
        
        if (!data.matches || data.matches.length === 0) {
            matchesContainer.innerHTML = '<p>No match data available for this round.</p>';
            return;
        }

        let tableHeader = `
            <thead>
                <tr>
                    <th class="team-home">Home</th>
                    <th class="th-center">Score</th>
                    <th class="team-away">Away</th>
                    <th class="th-center">Status</th>
                </tr>
            </thead>
        `;

        let tableBody = '<tbody>';
        data.matches.forEach(match => {
            const homeTeamName = match.home_team_greek || match.home_team || 'N/A';
            const awayTeamName = match.away_team_greek || match.away_team || 'N/A';
            const score = (match.score && match.score.trim()) ? match.score.trim() : '-';

            let statusHTML;
            switch(match.status) {
                case 'in_play':
                    statusHTML = `<span class="status in-play">Live <span class="live-minute">${match.live_minute}'</span></span>`;
                    break;
                case 'completed':
                    statusHTML = `<span class="status completed">Full Time</span>`;
                    break;
                case 'not_started':
                    const kickoff = formatGreekTime(match.date, match.kick_off_time_utc);
                    statusHTML = `<div class="status-time">${kickoff.date}</div><div class="status-time">${kickoff.time}</div>`;
                    break;
                default:
                    statusHTML = `<span class="status">${match.status || 'Scheduled'}</span>`;
            }

            tableBody += `
                <tr>
                    <td class="team-home">${homeTeamName}</td>
                    <td class="score">${score}</td>
                    <td class="team-away">${awayTeamName}</td>
                    <td class="status-cell">${statusHTML}</td>
                </tr>
            `;
        });
        tableBody += '</tbody>';

        matchesContainer.innerHTML = `<div class="table-container"><table class="match-table">${tableHeader}${tableBody}</table></div>`;
    }

    async function fetchData() {
        try {
            const response = await fetch(API_ENDPOINT);
            if (!response.ok) {
                throw new Error(`API responded with status: ${response.status}`);
            }
            const data = await response.json();
            
            errorMessage.classList.add('hidden');
            loadingSpinner.classList.add('hidden');
            
            renderTable(data);

        } catch (error) {
            console.error('Failed to fetch or render data:', error);
            loadingSpinner.classList.add('hidden');
            errorMessage.textContent = 'Could not load current match data. Please try again later.';
            errorMessage.classList.remove('hidden');
            matchesContainer.innerHTML = '';
        }
    }

    fetchData();
    setInterval(fetchData, REFRESH_INTERVAL_MS);
});
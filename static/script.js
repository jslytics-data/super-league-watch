document.addEventListener('DOMContentLoaded', function() {
    const API_ENDPOINT = '/api/get_current_round';
    const REFRESH_INTERVAL_MS = 30000;

    const mainTitle = document.getElementById('main-title');
    const lastUpdated = document.getElementById('last-updated');
    const matchesContainer = document.getElementById('matches-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const errorMessage = document.getElementById('error-message');

    let grTimezone;
    try {
        grTimezone = new Intl.DateTimeFormat().resolvedOptions().timeZone.includes("Europe") 
            ? 'Europe/Athens' 
            : undefined;
    } catch (e) {
        console.warn("Could not determine local timezone accurately.");
    }
    
    function formatGreekTime(dateStr, timeStr) {
        if (!grTimezone) return timeStr;
        if (!dateStr || !timeStr) return '';
        if (timeStr.length <= 2) timeStr += ':00';
        
        const utcDateTime = new Date(`${dateStr}T${timeStr}:00Z`);
        return new Intl.DateTimeFormat('en-GB', {
            hour: '2-digit',
            minute: '2-digit',
            timeZone: grTimezone,
            hour12: false
        }).format(utcDateTime);
    }

    function renderTable(data) {
        const competitionName = data.competition_name || 'Super League';
        const roundId = data.round_id || 'N/A';
        mainTitle.textContent = `${competitionName} - Round ${roundId}`;

        let lastUpdatedText = 'Last Updated: Just now';
        if (data.last_updated_utc) {
            const updatedDate = new Date(data.last_updated_utc);
            const options = {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            };
            if (grTimezone) {
                options.timeZone = grTimezone;
            }
            lastUpdatedText = `Last Updated: ${updatedDate.toLocaleTimeString('en-GB', options)}`;
        }
        lastUpdated.textContent = lastUpdatedText;
        
        if (!data.matches || data.matches.length === 0) {
            matchesContainer.innerHTML = '<p>No match data available for this round.</p>';
            return;
        }

        let tableHTML = '<div class="table-container"><table class="match-table">';
        data.matches.forEach(match => {
            const homeTeamName = match.home_team_greek || match.home_team || 'N/A';
            const awayTeamName = match.away_team_greek || match.away_team || 'N/A';
            const score = (match.score && match.score.trim()) ? match.score.trim() : '-';

            let statusHTML;
            switch(match.status) {
                case 'in_play':
                    statusHTML = `<div class="live-indicator">LIVE</div><div class="status-info">${match.live_minute}'</div>`;
                    break;
                case 'completed':
                    statusHTML = `<div class="status-info">Full Time</div>`;
                    break;
                case 'not_started':
                    const localTime = formatGreekTime(match.date, match.kick_off_time_utc);
                    statusHTML = `<div class="status-info">${match.date}</div><div class="status-info">${localTime}</div>`;
                    break;
                default:
                    statusHTML = `<div class="status-info">${match.status || 'Scheduled'}</div>`;
            }

            tableHTML += `
                <tr>
                    <td class="team-home">${homeTeamName}</td>
                    <td class="score">${score}</td>
                    <td class="team-away">${awayTeamName}</td>
                    <td class="status">${statusHTML}</td>
                </tr>
            `;
        });
        tableHTML += '</table></div>';
        matchesContainer.innerHTML = tableHTML;
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
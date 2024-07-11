import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import threading

app = Flask(__name__)

# Global variables
stories = []
last_update = None
update_lock = threading.Lock()

def sort_stories_by_votes(hnlist):
    return sorted(hnlist, key=lambda k:k['votes'], reverse=True)

def fetch_stories():
    global stories, last_update
    print("Fetching new stories...")
    res = requests.get('https://news.ycombinator.com/news')
    soup = BeautifulSoup(res.text, 'html.parser')
    links = soup.select('.titleline > a')
    subtext = soup.select('.subtext')
    
    hn = []
    for idx, item in enumerate(links):
        title = item.getText()
        href = item.get('href', None)
        vote = subtext[idx].select('.score')
        if len(vote):
            points = int(vote[0].getText().replace(' points',''))
            if points > 99:
                hn.append({'title': title, 'link': href, 'votes': points})
    
    with update_lock:
        stories = sort_stories_by_votes(hn)
        last_update = datetime.datetime.now()

def background_update():
    with app.app_context():
        fetch_stories()

scheduler = BackgroundScheduler()
scheduler.add_job(func=background_update, trigger="interval", minutes=15)
scheduler.start()

@app.route('/')
def home():
    global stories, last_update
    page = request.args.get('page', 1, type=int)
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    
    with update_lock:
        paginated_stories = stories[start:end]
        total_pages = -(-len(stories) // per_page)  # Ceiling division
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hacker News Top Stories</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0 auto; max-width: 800px; padding: 20px; line-height: 1.6; }
            h1 { color: #ff6600; }
            ol { padding-left: 20px; }
            li { margin-bottom: 15px; }
            a { color: #000; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .votes { color: #828282; font-size: 0.8em; }
            .pagination { margin-top: 20px; text-align: center; }
            .pagination a { margin: 0 5px; padding: 5px 10px; border: 1px solid #ddd; }
            .current-page { font-weight: bold; }
            #lastUpdate { color: #828282; font-size: 0.8em; margin-top: 20px; }
            #refreshButton { margin-top: 10px; }
            .loading { display: none; }
        </style>
    </head>
    <body>
        <h1>Hacker News Top Stories</h1>
        <div id="storiesList">
            <ol start="{{ start + 1 }}">
            {% for story in stories %}
                <li>
                    <a href="{{ story['link'] }}" target="_blank">{{ story['title'] }}</a>
                    <span class="votes">({{ story['votes'] }} votes)</span>
                </li>
            {% endfor %}
            </ol>
        </div>
        
        <div class="pagination">
            {% if page > 1 %}
                <a href="?page={{ page - 1 }}">&laquo; Previous</a>
            {% endif %}
            
            {% for p in range(1, total_pages + 1) %}
                {% if p == page %}
                    <span class="current-page">{{ p }}</span>
                {% else %}
                    <a href="?page={{ p }}">{{ p }}</a>
                {% endif %}
            {% endfor %}
            
            {% if page < total_pages %}
                <a href="?page={{ page + 1 }}">Next &raquo;</a>
            {% endif %}
        </div>
        
        <div id="lastUpdate">Last updated: <span id="updateTime">{{ last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else 'Never' }}</span></div>
        <button id="refreshButton">Refresh Stories</button>
        <div id="loading" class="loading">Loading...</div>
        
        <script>
            document.getElementById('refreshButton').addEventListener('click', function() {
                var loading = document.getElementById('loading');
                var storyList = document.getElementById('storiesList');
                var lastUpdate = document.getElementById('updateTime');
                
                loading.style.display = 'block';
                storyList.style.opacity = '0.5';
                
                fetch('/refresh', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        var ol = document.createElement('ol');
                        ol.start = {{ start + 1 }};
                        data.stories.forEach(function(story) {
                            var li = document.createElement('li');
                            var a = document.createElement('a');
                            a.href = story.link;
                            a.target = '_blank';
                            a.textContent = story.title;
                            var span = document.createElement('span');
                            span.className = 'votes';
                            span.textContent = `(${story.votes} votes)`;
                            li.appendChild(a);
                            li.appendChild(span);
                            ol.appendChild(li);
                        });
                        storyList.innerHTML = '';
                        storyList.appendChild(ol);
                        lastUpdate.textContent = data.last_update;
                        loading.style.display = 'none';
                        storyList.style.opacity = '1';
                    });
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html, stories=paginated_stories, page=page, total_pages=total_pages, start=start, last_update=last_update)

@app.route('/refresh', methods=['POST'])
def refresh():
    fetch_stories()
    return jsonify({
        'stories': stories[:10],  # Return only first 10 for the first page
        'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else 'Never'
    })

if __name__ == '__main__':
    fetch_stories()  # Initial fetch
    app.run(debug=True)
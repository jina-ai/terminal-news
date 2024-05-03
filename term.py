from datetime import datetime, timezone
import humanize
from textual import work
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Header, Footer, MarkdownViewer
from markdownify import markdownify
import aiohttp

import os

API_KEY = os.getenv('GHOST_API_KEY')
GHOST_URL = os.getenv('GHOST_URL', 'https://jina-ai-gmbh.ghost.io')


async def fetch_post_details(post_slug, base_url=GHOST_URL, api_key=API_KEY):
    headers = {'Authorization': f'Ghost {api_key}'}
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/ghost/api/v3/content/posts/slug/{post_slug}/?key={api_key}&fields=title,slug,html,created_at&include=authors"
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()
            # Check if there are posts returned
            if data['posts']:
                return data['posts'][0]
            else:
                return None


async def fetch_all_posts(base_url=GHOST_URL, api_key=API_KEY):
    headers = {'Authorization': f'Ghost {api_key}'}
    limit = 100
    page = 1
    all_posts = []

    async with aiohttp.ClientSession() as session:
        while True:
            url = f"{base_url}/ghost/api/v3/content/posts/?key={api_key}&limit={limit}&page={page}&fields=title,slug,created_at&include=authors"
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                posts = data['posts']
                if not posts:
                    break
                all_posts.extend(posts)
                page += 1
    return all_posts


class MarkdownBlog(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Return")]

    def __init__(self, slug: str) -> None:
        self.blog_slug = slug
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MarkdownViewer(self.blog_slug, show_table_of_contents=False)
        yield Footer()

    def on_mount(self) -> None:
        md = self.query_one(MarkdownViewer)
        md.loading = True
        self.load_data(md)

    @work
    async def load_data(self, md: MarkdownViewer) -> None:
        post = await fetch_post_details(self.blog_slug)
        self.title = 'Jina AI'
        self.sub_title = post['title']
        doc = markdownify(post['html'])

        md.document.update(doc)
        md.loading = False
        md.focus()


class JinaAI(App):
    BINDINGS = [("d", "toggle_dark", "Dark/Light"),
                ("q", "quit", "Quit")]

    def _human_readable_date(self, date_str):
        # Convert the ISO 8601 string into a datetime object directly
        dt = datetime.fromisoformat(date_str.rstrip('Z'))  # Remove the 'Z' if it's there
        if date_str.endswith('Z'):
            dt = dt.replace(tzinfo=timezone.utc)  # Explicitly set UTC if the 'Z' was present

        # Calculate the time difference in a human-readable format
        return humanize.naturaltime(datetime.now(timezone.utc) - dt)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable()
        yield Footer()

    @work
    async def load_data(self, table: DataTable) -> None:
        self._posts = await fetch_all_posts()
        table.add_rows((post['title'],
                        self._human_readable_date(post['created_at']),
                        ', '.join(author['name'] for author in post['authors']),
                        ) for post in self._posts)
        table.loading = False
        table.focus()

    def on_mount(self) -> None:
        self.title = 'Jina AI'
        self.sub_title = 'Your Search Foundation, Supercharged!'
        self.action_refresh()

    def on_data_table_row_selected(self, event):
        self.push_screen(MarkdownBlog(self._posts[event.cursor_row]['slug']))

    def action_refresh(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        table.cursor_type = 'row'
        table.add_columns('Title', 'Posted', 'Authors')
        table.loading = True
        self.load_data(table)

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark


if __name__ == "__main__":
    app = JinaAI()
    app.run()

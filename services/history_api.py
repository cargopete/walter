import openai
import os
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import random
import json

logger = logging.getLogger('walter.history_api')

class HistoryAPI:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
    
    async def get_events_for_date(self, month: int, day: int) -> List[Dict]:
        """Fetch historical events for a specific date using GPT-4o"""

        # Convert month number to name for better readability
        month_names = ["", "January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
        month_name = month_names[month]

        prompt = f"""Please provide a list of 15-20 notable historical events, births, and deaths that occurred on {month_name} {day}.

Requirements:
- Include a mix of events, births, and deaths from different time periods
- Focus on genuinely significant historical moments (wars, discoveries, inventions, political events, etc.)
- Prefer events that are at least 50 years old
- Include the specific year for each event
- Provide a brief but clear description of each event

Return the data as a JSON array with this exact structure:
[
  {{
    "type": "event",
    "year": "1969",
    "description": "Apollo 11 landed on the Moon"
  }},
  {{
    "type": "birth",
    "year": "1809",
    "description": "Charles Darwin was born"
  }},
  {{
    "type": "death",
    "year": "1965",
    "description": "Winston Churchill died"
  }}
]

Provide ONLY the JSON array, no other text."""

        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()

            def api_call():
                return self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a historical research assistant. Provide accurate historical information in the requested JSON format."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.7
                )

            response = await loop.run_in_executor(None, api_call)
            content = response.choices[0].message.content.strip()

            # Parse JSON response
            # Sometimes GPT-4o wraps JSON in markdown code blocks, so handle that
            if content.startswith("```"):
                # Extract JSON from code block
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            all_events = json.loads(content)

            logger.info(f"Fetched {len(all_events)} events from GPT-4o for {month}/{day}")
            return all_events

        except Exception as e:
            logger.error(f"Error fetching historical events from GPT-4o: {e}")
            return self._get_fallback_events(month, day)
    
    def select_best_event(self, events: List[Dict]) -> Dict:
        """Select the most interesting event from the list"""

        if not events:
            return self._get_fallback_event()

        # Filter out very recent events (less interesting for Victorian commentary)
        current_year = datetime.now().year
        historical_events = [
            e for e in events
            if e.get('year') and (
                isinstance(e['year'], str) and e['year'].isdigit() and int(e['year']) < current_year - 50
                or isinstance(e['year'], int) and e['year'] < current_year - 50
            )
        ]

        # If no historical events, use all events
        if not historical_events:
            historical_events = events

        # Prefer events with interesting keywords
        interesting_keywords = [
            'invented', 'discovered', 'war', 'revolution', 'expedition',
            'founded', 'abolished', 'assassinated', 'crowned', 'treaty',
            'exploration', 'scientific', 'disaster', 'miracle', 'scandal'
        ]

        scored_events = []
        for event in historical_events:
            score = 0
            desc = event.get('description', '').lower()

            # Check for interesting keywords
            for keyword in interesting_keywords:
                if keyword in desc:
                    score += 10

            # Prefer events (over births/deaths)
            if event.get('type') == 'event':
                score += 5

            # Prefer events with good descriptions
            if len(desc) > 50:
                score += 3

            scored_events.append((score, event))

        # Sort by score and add randomness to top choices
        scored_events.sort(key=lambda x: x[0], reverse=True)

        # Select randomly from top 3 events (if available)
        top_events = scored_events[:min(3, len(scored_events))]

        if top_events:
            selected = random.choice(top_events)[1]
            logger.info(f"Selected event: {selected.get('year')} - {selected.get('description')[:100]}...")
            return selected

        return self._get_fallback_event()

    def select_best_events(self, events: List[Dict], count: int = 5) -> List[Dict]:
        """Select multiple interesting events from the list"""

        if not events:
            return [self._get_fallback_event()]

        # Filter out very recent events (less interesting for Victorian commentary)
        current_year = datetime.now().year
        historical_events = [
            e for e in events
            if e.get('year') and (
                isinstance(e['year'], str) and e['year'].isdigit() and int(e['year']) < current_year - 50
                or isinstance(e['year'], int) and e['year'] < current_year - 50
            )
        ]

        # If no historical events, use all events
        if not historical_events:
            historical_events = events

        # Prefer events with interesting keywords
        interesting_keywords = [
            'invented', 'discovered', 'war', 'revolution', 'expedition',
            'founded', 'abolished', 'assassinated', 'crowned', 'treaty',
            'exploration', 'scientific', 'disaster', 'miracle', 'scandal'
        ]

        scored_events = []
        for event in historical_events:
            score = 0
            desc = event.get('description', '').lower()

            # Check for interesting keywords
            for keyword in interesting_keywords:
                if keyword in desc:
                    score += 10

            # Prefer events (over births/deaths)
            if event.get('type') == 'event':
                score += 5

            # Prefer events with good descriptions
            if len(desc) > 50:
                score += 3

            scored_events.append((score, event))

        # Sort by score
        scored_events.sort(key=lambda x: x[0], reverse=True)

        # Select top N events
        selected_events = [event for score, event in scored_events[:count]]

        # Ensure we have at least some events
        if not selected_events:
            selected_events = [self._get_fallback_event()]

        logger.info(f"Selected {len(selected_events)} events for today")
        for event in selected_events:
            logger.info(f"  - {event.get('year')}: {event.get('description')[:80]}...")

        return selected_events
    
    def _get_fallback_events(self, month: int, day: int) -> List[Dict]:
        """Provide fallback events if API fails"""
        
        # Some interesting historical events as fallbacks
        fallback_events = [
            {
                'type': 'event',
                'year': '1666',
                'description': 'The Great Fire of London began in a bakery on Pudding Lane'
            },
            {
                'type': 'event', 
                'year': '1851',
                'description': 'The Great Exhibition opened in Hyde Park, London'
            },
            {
                'type': 'event',
                'year': '1837',
                'description': 'Queen Victoria ascended to the throne'
            },
            {
                'type': 'event',
                'year': '1605',
                'description': 'The Gunpowder Plot to blow up Parliament was discovered'
            },
            {
                'type': 'birth',
                'year': '1564',
                'description': 'William Shakespeare was born'
            },
            {
                'type': 'event',
                'year': '1825',
                'description': 'The first passenger railway opened between Stockton and Darlington'
            }
        ]
        
        logger.warning(f"Using fallback events for {month}/{day}")
        return fallback_events
    
    def _get_fallback_event(self) -> Dict:
        """Get a single fallback event"""
        return {
            'type': 'event',
            'year': '1843',
            'description': 'Charles Dickens published "A Christmas Carol", forever ruining December for those of us who prefer our spirits in bottles rather than chains'
        }

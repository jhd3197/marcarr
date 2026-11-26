// The v1 API as documentation data (from docs/design/api/logic.js). Static on purpose:
// it documents what other apps call, so it changes only with the API itself.

export type Scope = 'read' | 'propose' | 'review' | 'run';

export interface Endpoint {
  group: string;
  method: 'GET' | 'POST';
  path: string; // under /api/v1
  title: string;
  scope: Scope;
  params: { name: string; type: string; what: string }[];
  example: string; // path with sample values
  body: string | null; // JSON body for POST examples
  response: string;
}

export const ENDPOINTS: Endpoint[] = [
  {
    "group": "Titles",
    "method": "GET",
    "path": "/titles",
    "title": "List titles",
    "scope": "read",
    "params": [
      {
        "name": "type",
        "type": "movie | show",
        "what": "Only one kind"
      },
      {
        "name": "analysed",
        "type": "true | false",
        "what": "Only analysed, or only not"
      },
      {
        "name": "q",
        "type": "text",
        "what": "Part of the name"
      },
      {
        "name": "page",
        "type": "number",
        "what": "Page of results"
      }
    ],
    "example": "/titles?type=movie&analysed=true",
    "body": null,
    "response": "{\n  \"total\": 4,\n  \"page\": 1,\n  \"items\": [\n    {\n      \"id\": \"movie:tmdb:671\",\n      \"name\": \"Harry Potter and the Sorcerer's Stone\",\n      \"year\": 2001,\n      \"type\": \"movie\",\n      \"videos\": 1,\n      \"analysed\": true,\n      \"to_review\": 108\n    }\n  ]\n}"
  },
  {
    "group": "Titles",
    "method": "GET",
    "path": "/titles/{title}",
    "title": "One title and its videos",
    "scope": "read",
    "params": [
      {
        "name": "title",
        "type": "id",
        "what": "Like movie:tmdb:671"
      }
    ],
    "example": "/titles/movie:tmdb:671",
    "body": null,
    "response": "{\n  \"id\": \"movie:tmdb:671\",\n  \"name\": \"Harry Potter and the Sorcerer's Stone\",\n  \"year\": 2001,\n  \"collection\": \"Harry Potter\",\n  \"videos\": [\n    {\n      \"id\": \"7c9e21ab\",\n      \"edition\": \"Extended\",\n      \"duration\": 9530.56,\n      \"steps_done\": 7\n    }\n  ]\n}"
  },
  {
    "group": "Titles",
    "method": "GET",
    "path": "/titles/{title}/graph",
    "title": "Who is seen with whom",
    "scope": "read",
    "params": [
      {
        "name": "video",
        "type": "id",
        "what": "One edition (default: the current one)"
      },
      {
        "name": "through",
        "type": "number",
        "what": "Stop at this scene, so nothing later shows"
      }
    ],
    "example": "/titles/movie:tmdb:671/graph?through=40",
    "body": null,
    "response": "{\n  \"video\": \"7c9e21ab\",\n  \"total_scenes\": 212,\n  \"through\": 40,\n  \"scenes\": 40,\n  \"people\": [\n    {\n      \"id\": \"harry-potter\",\n      \"name\": \"Harry Potter\",\n      \"seconds\": 1480.5,\n      \"scenes\": [\n        1,\n        2,\n        5\n      ],\n      \"named\": 3,\n      \"first\": {\n        \"n\": 1,\n        \"start\": 0.0\n      },\n      \"gap\": {\n        \"from\": 12,\n        \"to\": 19,\n        \"start\": 1830.0,\n        \"end\": 2410.0,\n        \"seconds\": 580.0\n      },\n      \"partners\": [\n        {\n          \"id\": \"ron-weasley\",\n          \"scenes\": 21\n        }\n      ]\n    }\n  ],\n  \"pairs\": [\n    {\n      \"a\": \"harry-potter\",\n      \"b\": \"ron-weasley\",\n      \"scenes\": [\n        5,\n        6,\n        9\n      ],\n      \"seconds\": 960.0\n    }\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}",
    "title": "One video and its seven steps",
    "scope": "read",
    "params": [
      {
        "name": "video",
        "type": "id",
        "what": "One file of a title"
      }
    ],
    "example": "/videos/7c9e21ab",
    "body": null,
    "response": "{\n  \"id\": \"7c9e21ab\",\n  \"title\": \"movie:tmdb:671\",\n  \"edition\": \"Extended\",\n  \"duration\": 9530.56,\n  \"steps\": {\n    \"shots\": \"done\",\n    \"subtitles\": \"done\",\n    \"scenes\": \"done\",\n    \"signals\": \"done\",\n    \"cast\": \"done\",\n    \"faces\": \"done\",\n    \"tags\": \"done\"\n  },\n  \"scenes\": 144,\n  \"seconds_spent\": 2820,\n  \"ai_cost\": 0.41\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/analysis",
    "title": "Everything about a video in one file",
    "scope": "read",
    "params": [
      {
        "name": "video",
        "type": "id",
        "what": "One file of a title"
      }
    ],
    "example": "/videos/7c9e21ab/analysis",
    "body": null,
    "response": "{\n  \"format\": \"marcarr-analysis/1\",\n  \"title\": {\n    \"id\": \"movie:tmdb:671\",\n    \"name\": \"Harry Potter and the Sorcerer's Stone\",\n    \"year\": 2001\n  },\n  \"video\": {\n    \"id\": \"7c9e21ab\",\n    \"duration\": 9530.56\n  },\n  \"steps\": {\n    \"shots\": \"done\",\n    \"subtitles\": \"done\",\n    \"scenes\": \"done\",\n    \"signals\": \"done\",\n    \"cast\": \"done\",\n    \"faces\": \"done\",\n    \"tags\": \"done\"\n  },\n  \"shots\": [\n    \"...\"\n  ],\n  \"scenes\": [\n    {\n      \"n\": 101,\n      \"start\": 5390.0,\n      \"end\": 5587.0,\n      \"people\": [\n        \"harry-potter\",\n        \"ron-weasley\"\n      ],\n      \"tags\": [\n        \"Christmas\",\n        \"Magic\",\n        \"Friendship\"\n      ],\n      \"place\": \"hogwarts\",\n      \"still\": \"/api/v1/videos/7c9e21ab/scenes/101/still.jpg\"\n    }\n  ],\n  \"tags\": [\n    {\n      \"id\": \"tag_5021\",\n      \"tag\": \"Christmas\",\n      \"family\": \"Occasion\",\n      \"start\": 5390.0,\n      \"end\": 5587.0,\n      \"status\": \"proposed\",\n      \"source\": \"ai\",\n      \"people\": [\n        \"harry-potter\",\n        \"ron-weasley\"\n      ],\n      \"evidence\": {\n        \"heard\": [\n          \"Christmas\",\n          \"presents\"\n        ],\n        \"seen\": [\n          \"Christmas tree\",\n          \"wrapped presents\"\n        ]\n      }\n    }\n  ],\n  \"signals\": [\n    {\n      \"signal\": \"dark\",\n      \"start\": 5587.0,\n      \"end\": 5774.0\n    }\n  ],\n  \"people\": [\n    {\n      \"id\": \"ron-weasley\",\n      \"actor\": \"Rupert Grint\",\n      \"character\": \"Ron Weasley\"\n    }\n  ],\n  \"faces\": [\n    {\n      \"person\": \"ron-weasley\",\n      \"at\": 5398.0,\n      \"score\": 0.38\n    }\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/scenes",
    "title": "The scenes of a video",
    "scope": "read",
    "params": [
      {
        "name": "from",
        "type": "seconds",
        "what": "Start of the range"
      },
      {
        "name": "to",
        "type": "seconds",
        "what": "End of the range"
      },
      {
        "name": "tag",
        "type": "tag name",
        "what": "Only scenes with this tag"
      }
    ],
    "example": "/videos/7c9e21ab/scenes?from=5300&to=5600",
    "body": null,
    "response": "{\n  \"total\": 3,\n  \"items\": [\n    {\n      \"n\": 101,\n      \"start\": 5390.0,\n      \"end\": 5587.0,\n      \"people\": [\n        \"harry-potter\",\n        \"ron-weasley\"\n      ],\n      \"tags\": [\n        \"Christmas\",\n        \"Magic\",\n        \"Friendship\"\n      ],\n      \"place\": \"hogwarts\",\n      \"still\": \"/api/v1/videos/7c9e21ab/scenes/101/still.jpg\"\n    }\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/at/{seconds}",
    "title": "What is on screen at a time",
    "scope": "read",
    "params": [
      {
        "name": "seconds",
        "type": "number",
        "what": "Time in the video"
      }
    ],
    "example": "/videos/7c9e21ab/at/5400",
    "body": null,
    "response": "{\n  \"t\": 5400.0,\n  \"scene\": 101,\n  \"people\": [\n    \"harry-potter\",\n    \"ron-weasley\"\n  ],\n  \"tags\": [\n    {\n      \"tag\": \"Christmas\",\n      \"status\": \"proposed\"\n    },\n    {\n      \"tag\": \"Castle\",\n      \"status\": \"accepted\"\n    }\n  ],\n  \"place\": \"hogwarts\",\n  \"signals\": [\n    \"dialogue\"\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/scenes/{n}/brief",
    "title": "A scene as text to paste",
    "scope": "read",
    "params": [
      {
        "name": "link",
        "type": "url",
        "what": "Added at the end, to get back to the scene"
      }
    ],
    "example": "/videos/7c9e21ab/scenes/101/brief",
    "body": null,
    "response": "{\n  \"text\": \"Harry Potter and the Sorcerer's Stone (2001), Extended: scene 101, 1:29:50 to 1:33:07\\nSeen: Harry Potter, Ron Weasley\\nTags:\\n  Christmas (to review): heard: Merry Christmas (1:29:58)\"\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/tags",
    "title": "The tags on a video",
    "scope": "read",
    "params": [
      {
        "name": "status",
        "type": "proposed | accepted | rejected",
        "what": "Accepted when left out"
      },
      {
        "name": "family",
        "type": "family name",
        "what": "Only one family"
      },
      {
        "name": "source",
        "type": "person | ai | app name",
        "what": "Who proposed it"
      }
    ],
    "example": "/videos/7c9e21ab/tags?status=proposed&family=Occasion",
    "body": null,
    "response": "{\n  \"total\": 1,\n  \"items\": [\n    {\n      \"id\": \"tag_5021\",\n      \"tag\": \"Christmas\",\n      \"family\": \"Occasion\",\n      \"start\": 5390.0,\n      \"end\": 5587.0,\n      \"status\": \"proposed\",\n      \"source\": \"ai\",\n      \"people\": [\n        \"harry-potter\",\n        \"ron-weasley\"\n      ],\n      \"evidence\": {\n        \"heard\": [\n          \"Christmas\",\n          \"presents\"\n        ],\n        \"seen\": [\n          \"Christmas tree\",\n          \"wrapped presents\"\n        ]\n      }\n    }\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/signals",
    "title": "The measured signals of a video",
    "scope": "read",
    "params": [
      {
        "name": "signal",
        "type": "signal name",
        "what": "Like dark, silence, loud"
      }
    ],
    "example": "/videos/7c9e21ab/signals?signal=dark",
    "body": null,
    "response": "{\n  \"total\": 1,\n  \"items\": [\n    {\n      \"signal\": \"dark\",\n      \"start\": 5587.0,\n      \"end\": 5774.0\n    }\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "GET",
    "path": "/videos/{video}/faces",
    "title": "The faces found in a video",
    "scope": "read",
    "params": [
      {
        "name": "person",
        "type": "person id",
        "what": "Only one person"
      },
      {
        "name": "confirmed",
        "type": "true | false",
        "what": "Only sure ones, or only unsure"
      }
    ],
    "example": "/videos/7c9e21ab/faces?confirmed=false",
    "body": null,
    "response": "{\n  \"total\": 1,\n  \"items\": [\n    {\n      \"id\": \"face_88\",\n      \"person\": \"ron-weasley\",\n      \"at\": 5398.0,\n      \"score\": 0.38,\n      \"confirmed\": false\n    }\n  ]\n}"
  },
  {
    "group": "Videos",
    "method": "POST",
    "path": "/videos/{video}/run",
    "title": "Run steps again",
    "scope": "run",
    "params": [
      {
        "name": "steps",
        "type": "list",
        "what": "All seven when left out"
      }
    ],
    "example": "/videos/7c9e21ab/run",
    "body": "{\n  \"steps\": [\n    \"subtitles\",\n    \"scenes\",\n    \"tags\"\n  ]\n}",
    "response": "{\n  \"queued\": true,\n  \"position\": 2\n}"
  },
  {
    "group": "Search",
    "method": "GET",
    "path": "/search/scenes",
    "title": "Find scenes across the library",
    "scope": "read",
    "params": [
      {
        "name": "tags",
        "type": "list",
        "what": "A scene must have all of them"
      },
      {
        "name": "person",
        "type": "person id",
        "what": "Must be on screen"
      },
      {
        "name": "q",
        "type": "text",
        "what": "Words in the dialogue"
      },
      {
        "name": "status",
        "type": "accepted | proposed",
        "what": "Accepted when left out"
      },
      {
        "name": "title",
        "type": "id",
        "what": "Only one title"
      },
      {
        "name": "signals",
        "type": "list",
        "what": "Measured signals like dark or fast-cutting, each over at least half the scene"
      }
    ],
    "example": "/search/scenes?tags=Christmas&status=accepted",
    "body": null,
    "response": "{\n  \"total\": 8,\n  \"items\": [\n    {\n      \"title\": \"movie:tmdb:671\",\n      \"video\": \"7c9e21ab\",\n      \"scene\": 101,\n      \"start\": 5390.0,\n      \"end\": 5587.0,\n      \"tags\": [\n        \"Christmas\",\n        \"Magic\",\n        \"Friendship\"\n      ],\n      \"still\": \"/api/v1/videos/7c9e21ab/scenes/101/still.jpg\"\n    }\n  ]\n}"
  },
  {
    "group": "Search",
    "method": "GET",
    "path": "/collections",
    "title": "Saved searches and how many kept scenes match each",
    "scope": "read",
    "params": [],
    "example": "/collections",
    "body": null,
    "response": "{\n  \"total\": 1,\n  \"items\": [\n    {\n      \"id\": \"col_1a2b3c4d5e\",\n      \"name\": \"Christmas dinner\",\n      \"tags\": [\n        \"christmas\",\n        \"meal\"\n      ],\n      \"person\": null,\n      \"q\": \"\",\n      \"signals\": [],\n      \"created_at\": \"2026-11-26T18:04:11\",\n      \"scenes\": 12\n    }\n  ]\n}"
  },
  {
    "group": "Tags",
    "method": "GET",
    "path": "/tags",
    "title": "The tag list, with your own tags in mine",
    "scope": "read",
    "params": [
      {
        "name": "family",
        "type": "family name",
        "what": "Only one family"
      }
    ],
    "example": "/tags?family=Occasion",
    "body": null,
    "response": "{\n  \"mine\": [\n    {\n      \"id\": \"running-gag\",\n      \"name\": \"Running gag\",\n      \"family\": null,\n      \"hint\": \"The stapler goes missing again\",\n      \"see\": [\n        \"stapler\"\n      ],\n      \"hear\": [\n        \"where's my stapler\"\n      ],\n      \"counts\": {\n        \"accepted\": 3,\n        \"proposed\": 1,\n        \"rejected\": 0\n      },\n      \"label\": false,\n      \"custom\": true,\n      \"scope\": {\n        \"title\": \"show:tvdb:73244\",\n        \"name\": \"The Office\",\n        \"type\": \"show\",\n        \"year\": 2005\n      },\n      \"retired\": false,\n      \"created_at\": \"2026-11-26T18:04:11\"\n    }\n  ],\n  \"families\": [\n    {\n      \"family\": \"Occasion\",\n      \"tags\": [\n        {\n          \"tag\": \"Christmas\",\n          \"hint\": \"A scene set at Christmas\",\n          \"see\": [\n            \"Christmas tree\",\n            \"presents\"\n          ],\n          \"hear\": [\n            \"Christmas\"\n          ]\n        }\n      ]\n    }\n  ]\n}"
  },
  {
    "group": "Tags",
    "method": "POST",
    "path": "/videos/{video}/tags",
    "title": "Propose a tag",
    "scope": "propose",
    "params": [
      {
        "name": "tag",
        "type": "tag name",
        "what": "From the tag list"
      },
      {
        "name": "start",
        "type": "seconds",
        "what": "Where it starts"
      },
      {
        "name": "end",
        "type": "seconds",
        "what": "Where it ends"
      },
      {
        "name": "people",
        "type": "list",
        "what": "Who is in it"
      },
      {
        "name": "evidence",
        "type": "heard, seen",
        "what": "Why"
      }
    ],
    "example": "/videos/7c9e21ab/tags",
    "body": "{\n  \"tag\": \"Snow\",\n  \"start\": 5332.0,\n  \"end\": 5390.0,\n  \"evidence\": {\n    \"seen\": [\n      \"snow at the windows\"\n    ]\n  }\n}",
    "response": "{\n  \"id\": \"tag_5022\",\n  \"tag\": \"Snow\",\n  \"status\": \"proposed\",\n  \"source\": \"doblarr\"\n}"
  },
  {
    "group": "People and places",
    "method": "POST",
    "path": "/videos/{video}/presence",
    "title": "Report who is seen, heard or named",
    "scope": "propose",
    "params": [
      {
        "name": "person",
        "type": "id",
        "what": "A person id"
      },
      {
        "name": "how",
        "type": "seen | mentioned | speaker",
        "what": "How they are in it"
      },
      {
        "name": "start, end",
        "type": "seconds",
        "what": "The stretch"
      },
      {
        "name": "at",
        "type": "seconds",
        "what": "The moment that shows it"
      }
    ],
    "example": "/videos/7c9e21ab/presence",
    "body": "{\n  \"person\": \"ron-weasley\",\n  \"how\": \"speaker\",\n  \"start\": 5340.0,\n  \"end\": 5344.5,\n  \"at\": 5341.0\n}",
    "response": "{\n  \"id\": \"pre_51c0\",\n  \"person\": \"ron-weasley\",\n  \"how\": \"speaker\",\n  \"status\": \"proposed\",\n  \"source\": \"doblarr\"\n}"
  },
  {
    "group": "Tags",
    "method": "POST",
    "path": "/tags/{tag}/keep",
    "title": "Keep a tag",
    "scope": "review",
    "params": [
      {
        "name": "tag",
        "type": "id",
        "what": "A proposed tag"
      }
    ],
    "example": "/tags/tag_5021/keep",
    "body": null,
    "response": "{\n  \"id\": \"tag_5021\",\n  \"status\": \"accepted\"\n}"
  },
  {
    "group": "Tags",
    "method": "POST",
    "path": "/tags/{tag}/drop",
    "title": "Drop a tag",
    "scope": "review",
    "params": [
      {
        "name": "tag",
        "type": "id",
        "what": "A proposed tag"
      }
    ],
    "example": "/tags/tag_5021/drop",
    "body": null,
    "response": "{\n  \"id\": \"tag_5021\",\n  \"status\": \"rejected\"\n}"
  },
  {
    "group": "People and places",
    "method": "GET",
    "path": "/people/{person}/scenes",
    "title": "Every scene with a person",
    "scope": "read",
    "params": [
      {
        "name": "person",
        "type": "person id",
        "what": "A cast member"
      },
      {
        "name": "title",
        "type": "id",
        "what": "Only one title"
      }
    ],
    "example": "/people/ron-weasley/scenes",
    "body": null,
    "response": "{\n  \"person\": {\n    \"id\": \"ron-weasley\",\n    \"actor\": \"Rupert Grint\",\n    \"character\": \"Ron Weasley\"\n  },\n  \"total\": 31,\n  \"items\": [\n    {\n      \"title\": \"movie:tmdb:671\",\n      \"video\": \"7c9e21ab\",\n      \"scene\": 34,\n      \"start\": 2178.0,\n      \"end\": 2388.0\n    }\n  ]\n}"
  },
  {
    "group": "People and places",
    "method": "GET",
    "path": "/places/{place}/scenes",
    "title": "Every scene set in a named place",
    "scope": "read",
    "params": [
      {
        "name": "place",
        "type": "place id",
        "what": "Like hogwarts/great-hall"
      }
    ],
    "example": "/places/hogwarts/great-hall/scenes",
    "body": null,
    "response": "{\n  \"place\": {\n    \"id\": \"hogwarts/great-hall\",\n    \"name\": \"Great Hall\",\n    \"inside\": \"hogwarts\",\n    \"implies\": [\n      \"Castle\",\n      \"School\"\n    ]\n  },\n  \"total\": 9,\n  \"items\": [\n    {\n      \"title\": \"movie:tmdb:671\",\n      \"video\": \"7c9e21ab\",\n      \"scene\": 47,\n      \"start\": 2892.0,\n      \"end\": 3147.0\n    }\n  ]\n}"
  },
  {
    "group": "System",
    "method": "GET",
    "path": "/status",
    "title": "The queue and this month",
    "scope": "read",
    "params": [],
    "example": "/status",
    "body": null,
    "response": "{\n  \"queue\": {\n    \"running\": 1,\n    \"waiting\": 2\n  },\n  \"ai\": {\n    \"month_cost\": 2.01,\n    \"month_limit\": 10.0\n  },\n  \"plex\": \"connected\"\n}"
  }
];

/** Webhook events and a sample payload for each. */
export const EVENTS: { name: string; what: string; payload: string }[] = [
  {
    "name": "step.finished",
    "what": "A step finished on a video",
    "payload": "{\n  \"event\": \"step.finished\",\n  \"video\": \"7c9e21ab\",\n  \"title\": \"movie:tmdb:671\",\n  \"step\": \"tags\",\n  \"state\": \"done\",\n  \"seconds\": 988\n}"
  },
  {
    "name": "video.analysed",
    "what": "All seven steps are done",
    "payload": "{\n  \"event\": \"video.analysed\",\n  \"video\": \"7c9e21ab\",\n  \"title\": \"movie:tmdb:671\",\n  \"seconds_spent\": 2820,\n  \"ai_cost\": 0.41\n}"
  },
  {
    "name": "tag.proposed",
    "what": "A tag is waiting for review",
    "payload": "{\n  \"event\": \"tag.proposed\",\n  \"tag\": {\n    \"id\": \"tag_5021\",\n    \"tag\": \"Christmas\",\n    \"family\": \"Occasion\",\n    \"start\": 5390.0,\n    \"end\": 5587.0,\n    \"status\": \"proposed\",\n    \"source\": \"ai\",\n    \"people\": [\n      \"harry-potter\",\n      \"ron-weasley\"\n    ],\n    \"evidence\": {\n      \"heard\": [\n        \"Christmas\",\n        \"presents\"\n      ],\n      \"seen\": [\n        \"Christmas tree\",\n        \"wrapped presents\"\n      ]\n    }\n  }\n}"
  },
  {
    "name": "tag.kept",
    "what": "A person kept a tag",
    "payload": "{\n  \"event\": \"tag.kept\",\n  \"id\": \"tag_5021\",\n  \"tag\": \"Christmas\",\n  \"video\": \"7c9e21ab\"\n}"
  },
  {
    "name": "tag.dropped",
    "what": "A person dropped a tag",
    "payload": "{\n  \"event\": \"tag.dropped\",\n  \"id\": \"tag_5021\",\n  \"tag\": \"Christmas\",\n  \"video\": \"7c9e21ab\"\n}"
  },
  {
    "name": "labels.written",
    "what": "Labels were written to Plex",
    "payload": "{\n  \"event\": \"labels.written\",\n  \"title\": \"movie:tmdb:671\",\n  \"labels\": [\n    \"marcarr:christmas\",\n    \"marcarr:snow\"\n  ]\n}"
  }
];

export const MCP_CONFIG = "{\n  \"mcpServers\": {\n    \"marcarr\": {\n      \"command\": \"marcarr\",\n      \"args\": [\n        \"mcp\"\n      ]\n    }\n  }\n}";

export const USERS: Record<Scope, string[]> = {
  read: ['FansCut', 'Doblarr', 'MCP clients'],
  propose: ['FansCut', 'Doblarr', 'MCP clients'],
  review: ['The review pages'],
  run: ['FansCut'],
};

export const TOOLS: { name: string; what: string; path: string; scope: Scope }[] = [
  { name: 'find_scenes', what: 'Find scenes by tag, person, words or signal', path: 'GET /search/scenes', scope: 'read' },
  { name: 'list_collections', what: 'The saved searches', path: 'GET /collections', scope: 'read' },
  { name: 'whats_at', what: 'What is on screen at a time', path: 'GET /videos/{video}/at/{seconds}', scope: 'read' },
  { name: 'get_scene', what: 'One scene with its tags and people', path: 'GET /videos/{video}/scenes', scope: 'read' },
  { name: 'list_tags', what: 'The tag list', path: 'GET /tags', scope: 'read' },
  { name: 'propose_tag', what: 'Propose a tag for review', path: 'POST /videos/{video}/tags', scope: 'propose' },
];

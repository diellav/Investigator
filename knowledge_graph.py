import json
from pathlib import Path

INPUT = Path("output/processed_dataset.json")
OUTPUT = Path("output/knowledge_graph.json")

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = []
edges = []

node_ids = set()
edge_ids = set()


def add_node(node_id, node_type, **properties):
    if node_id not in node_ids:
        node = {
            "id": node_id,
            "type": node_type
        }
        node.update(properties)
        nodes.append(node)
        node_ids.add(node_id)


def add_edge(source, target, relationship):
    edge = (source, target, relationship)

    if edge not in edge_ids:

        edges.append({
            "source": source,
            "target": target,
            "relationship": relationship
        })

        edge_ids.add(edge)


####################################################
# CLIENT
####################################################

client = data["client"]

client_id = f"client:{client['client_id']}"

add_node(

    client_id,

    "Client",

    hostname=client["hostname"],
    os=client["operating_system"]
)

####################################################
# INCIDENT RESPONSE AGENT
####################################################

agent = client["incident_response_agent"]

agent_id = f"agent:{agent['name']}"

add_node(

    agent_id,

    "IncidentResponseAgent",

    name=agent["name"],
    version=agent["version"]
)

add_edge(

    client_id,

    agent_id,

    "HAS_AGENT"
)

####################################################
# COLLECTION
####################################################

collection = data["collection"]

collection_id = f"collection:{collection['session_id']}"

add_node(

    collection_id,

    "Collection",

    creator=collection["creator"]
)

add_edge(

    client_id,

    collection_id,

    "HAS_COLLECTION"
)

####################################################
# ARTIFACTS
####################################################

for artifact in collection["artifacts"]:

    artifact_id = f"artifact:{artifact}"

    add_node(

        artifact_id,

        "Artifact",

        name=artifact
    )

    add_edge(

        collection_id,

        artifact_id,

        "COLLECTED_ARTIFACT"
    )

####################################################
# USERS
####################################################

for username in data["summary"]["identified_usernames"]:

    user_id = f"user:{username}"

    add_node(

        user_id,

        "User",

        username=username
    )

####################################################
# APPLICATIONS
####################################################

for app in data["summary"]["identified_applications"]:

    app_id = f"app:{app}"

    add_node(

        app_id,

        "Application",

        name=app
    )

####################################################
# FILES
####################################################

for upload in data["uploads"]:

    file_id = f"file:{upload['path']}"

    add_node(

        file_id,

        "File",

        path=upload["path"],
        extension=upload["extension"],
        file_size=upload["file_size"]
    )

    #######################################
    # USER -> FILE
    #######################################

    if upload["username"]:

        user_id = f"user:{upload['username']}"

        add_edge(

            user_id,

            file_id,

            "OWNS_FILE"
        )

    #######################################
    # APPLICATION -> FILE
    #######################################

    if upload["application"]:

        app_id = f"app:{upload['application']}"

        add_edge(

            app_id,

            file_id,

            "GENERATED_FILE"
        )

    #######################################
    # COLLECTION -> FILE
    #######################################

    add_edge(

        collection_id,

        file_id,

        "COLLECTED"
    )

####################################################
# LOGS
####################################################

for log in data["logs"]:

    log_id = f"log:{log['record_id']}"

    add_node(

        log_id,

        "Log",

        timestamp=log["timestamp"],
        level=log["level"]
    )

    add_edge(

        collection_id,

        log_id,

        "GENERATED_LOG"
    )

####################################################
# SAVE GRAPH
####################################################

graph = {

    "metadata":{

        "node_count":len(nodes),

        "edge_count":len(edges)

    },

    "nodes":nodes,

    "edges":edges

}

with open(

    OUTPUT,

    "w",

    encoding="utf-8"

) as f:

    json.dump(

        graph,

        f,

        indent=2,

        ensure_ascii=False

    )

print("Knowledge graph created.")
print("Nodes:",len(nodes))
print("Edges:",len(edges))
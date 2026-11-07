// Paste these into the Neo4j Browser (AuraDB console or http://localhost:7474) to look at the graph.

// 1. Everything (small graphs only)
MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m;

// 2. All captured knowledge with its device, author and source
MATCH (a:Assertion)-[:OBSERVED_ON]->(d:Device),
      (a)-[:BY]->(p:Person), (a)-[:FROM]->(s:Source)
RETURN a.id, d.node_id, p.name, s.channel, a.outcome, a.summary
ORDER BY a.valid_from;

// 3. THE KEY QUERY: what applies to TRN-077, even if TRN-077 was never mentioned?
//    (device itself OR matches the scope rule, and still valid)
MATCH (d:Device {node_id: "TRN-077"})
MATCH (a:Assertion)
WHERE a.valid_to IS NULL
  AND ( (a)-[:OBSERVED_ON]->(d)
        OR ( a.scope_node_type = d.node_type
             AND (a.scope_installed_before IS NULL OR d.install_date < a.scope_installed_before) ) )
RETURN a.id, a.summary, a.actions, a.avoid, a.outcome, a.confidence
ORDER BY a.confidence DESC;

// 4. The growing vocabulary: terms Gemini added automatically, and where they first appeared
MATCH (t:Term {status: 'new'})
RETURN t.category, t.name, t.first_seen_in, t.created_at ORDER BY t.created_at;

// 5. Merged wordings: which different phrasings were mapped onto an existing term
MATCH (t:Term) WHERE size(t.aliases) > 0
RETURN t.category, t.name, t.aliases;

// 6. Knowledge connected through shared terms: every tip that recommends bouncing an interface
MATCH (a:Assertion)-[:RECOMMENDS]->(:Term {name: 'BOUNCE_INTERFACE'})
MATCH (a)-[:OBSERVED_ON]->(d:Device)
RETURN a.id, d.node_id, a.outcome, a.summary;

// 7. Start over (deletes everything)
// MATCH (n) DETACH DELETE n;

// 8. How later messages changed earlier knowledge (reinforced / narrowed / superseded / conflicting)
MATCH (n:Assertion)-[r:REINFORCES|NARROWS_SCOPE|SUPERSEDES|CONFLICTS_WITH]->(c:Assertion)
RETURN n.id AS new_tip, type(r) AS relation, c.id AS older_tip, r.firmware_below, r.reason
ORDER BY n.id;

// 9. Knowledge that is no longer valid (has a valid_to), and disputed knowledge
MATCH (a:Assertion) WHERE a.valid_to IS NOT NULL OR a.status = 'disputed'
RETURN a.id, a.status, toString(a.valid_from) AS valid_from, toString(a.valid_to) AS valid_to, a.summary;

// 10. How each tip was linked to its device: by ID, nickname or place, and how sure
MATCH (a:Assertion)-[r:OBSERVED_ON]->(d:Device)
RETURN a.id, d.node_id, coalesce(r.linked_by, 'id') AS linked_by, r.link_confidence, r.via
ORDER BY linked_by DESC, a.id;

// 11. Sites: which devices are where, and knowledge reported at a site without naming a device
MATCH (s:Site)<-[:AT]-(d:Device)
OPTIONAL MATCH (a:Assertion)-[r:OBSERVED_AT]->(s)
RETURN s.name, collect(DISTINCT d.node_id) AS devices, collect(DISTINCT a.id) AS site_tips;

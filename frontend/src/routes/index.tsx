import { createFileRoute } from "@tanstack/react-router";
import { AssistantApp } from "@/components/assistant/AssistantApp";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "EVISA — Network knowledge assistant" },
      {
        name: "description",
        content: "Ask about a network device, a symptom or a fix and get answers from captured expert knowledge.",
      },
      { property: "og:title", content: "EVISA — Network knowledge assistant" },
      {
        property: "og:description",
        content: "Field answers for transmission, base station, router and microwave issues.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AssistantApp,
});

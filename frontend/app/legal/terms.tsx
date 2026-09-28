import { LegalPage } from "@/src/components/LegalPage";

const sections = [
  {
    heading: "Using ShortCut AI",
    body: "You may use ShortCut AI only in compliance with applicable law and these terms. You are responsible for your account, the media you upload, the instructions you provide and the way you use or publish generated outputs.",
  },
  {
    heading: "Your content",
    body: "You retain ownership of content you own. You grant ShortCut AI the limited rights needed to host, process, transform and deliver your content and requested outputs. You must have the rights and permissions necessary to upload and process the material you submit.",
  },
  {
    heading: "AI-assisted output",
    body: "AI-assisted edits, captions, analysis and recommendations can be incomplete or inaccurate. Review outputs before publishing or relying on them. ShortCut AI does not guarantee that an edit, caption, claim, music choice or other generated result is suitable for a particular use.",
  },
  {
    heading: "Prohibited use",
    body: "Do not use the service to violate law, infringe intellectual-property or privacy rights, distribute malware, abuse service infrastructure, evade usage controls, impersonate others, or process material you are not authorized to use.",
  },
  {
    heading: "Beta availability and limits",
    body: "During beta periods, features, quotas and availability may change. We may impose file, storage, AI and render limits to protect reliability and control abuse. We may suspend access when necessary to protect users, infrastructure or the service.",
  },
  {
    heading: "Account termination and deletion",
    body: "You can delete your account from the product. We may restrict or terminate accounts that materially violate these terms, applicable law or service-security requirements.",
  },
  {
    heading: "Disclaimers and liability",
    body: "The service is provided on an as-available basis to the extent permitted by applicable law. Nothing in these terms excludes rights or liabilities that cannot legally be excluded. Final commercial terms, governing law and any paid-plan terms should be reviewed for the operator's launch jurisdiction before paid public release.",
  },
];

export default function TermsOfService() {
  return <LegalPage title="Terms of Service" sections={sections} />;
}

import { LegalPage } from "@/src/components/LegalPage";

const sections = [
  {
    heading: "Information we process",
    body: "ShortCut AI processes account details, project metadata, uploaded video, audio and images, editing instructions, generated project state, exports, service logs and security events needed to provide and protect the service.",
  },
  {
    heading: "How media and AI are used",
    body: "Uploaded media is processed to provide editing features such as transcription, visual analysis, retrieval, planning and rendering. Configured AI providers may receive the minimum content needed for those features. ShortCut AI does not use a creator's private media for advertising.",
  },
  {
    heading: "Storage and security",
    body: "Production media is stored in private object storage and application records are stored in the production database. Access is limited to the service components and authorized operators needed to run, secure and support the product. Transport uses HTTPS in production.",
  },
  {
    heading: "Retention and deletion",
    body: "We retain account and project data while the account is active and as needed to operate the service. Users can permanently delete their account from Profile. Account deletion removes user-scoped application records and media stored under that account, subject to short-lived infrastructure backups or logs that expire under operational retention policies.",
  },
  {
    heading: "Service providers",
    body: "ShortCut AI may use infrastructure, database, object-storage, AI, email-delivery, error-monitoring and hosting providers to operate the service. These providers process information only for the purposes needed to deliver their respective services.",
  },
  {
    heading: "Your choices",
    body: "You can update profile information, remove individual assets and projects, or delete your account. You may contact the support address shown above for privacy questions or requests that cannot be completed in the product.",
  },
  {
    heading: "Children and changes",
    body: "ShortCut AI is not intended for children who cannot legally consent to use the service in their jurisdiction. We may update this policy as the product changes and will publish the current effective date here.",
  },
];

export default function PrivacyPolicy() {
  return <LegalPage title="Privacy Policy" sections={sections} />;
}

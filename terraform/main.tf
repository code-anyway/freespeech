provider "google" {
  region  = "europe-central2"
  zone    = "europe-central2-c"
  project = "freespeech-staging-alex-1"
}

variable "gcp_service_list" {
  description = "The list of apis necessary for the project"
  type        = list(string)
  default     = [
    # these are from experiment. Discuss if we need them.
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "compute.googleapis.com",
    "secretmanager.googleapis.com",

    # todo clean these up so that only used ones remain
    # these come from existing dev account
    "bigquery.googleapis.com",
    "bigquerymigration.googleapis.com",
    "bigquerystorage.googleapis.com",
    "cloudapis.googleapis.com",
    "cloudbuild.googleapis.com",
    "clouddebugger.googleapis.com",
    "cloudtrace.googleapis.com",
    "containeranalysis.googleapis.com",
    "containerregistry.googleapis.com",
    "datastore.googleapis.com",
    "firebaserules.googleapis.com",
    "firestore.googleapis.com",
    "firestorekeyvisualizer.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "servicemanagement.googleapis.com",
    "serviceusage.googleapis.com",
    "speech.googleapis.com",
    "sql-component.googleapis.com",
    "storage-api.googleapis.com",
    "storage-component.googleapis.com",
    "storage.googleapis.com",
    "texttospeech.googleapis.com",
    "translate.googleapis.com",

  ]
}

resource "google_project_service" "gcp_services" {
  for_each           = toset(var.gcp_service_list)
  service            = each.key
  disable_on_destroy = false
}

data "google_project" "project" {
}

locals {
  secrets = [
    "TELEGRAM_BOT_TOKEN",
    "DEEPGRAM_KEY",
    "AZURE_CONVERSATIONS_TOKEN",
    "AZURE_SUBSCRIPTION_KEY",
    "NOTION_TOKEN"
  ]
  region       = "europe-central2"
  azure_region = "eastus"
}

resource "google_secret_manager_secret" "secret" {
  for_each  = toset(local.secrets)
  secret_id = each.key
  replication {
    automatic = true
  }
}

#todo do we need a secret version? If we don't do it, cloud run would fail and the
# plan would not complete from the first time. If we do, there is some grabage in the
# config we should not forget changing to real secrets

resource "google_secret_manager_secret_iam_member" "secret-access" {
  for_each  = toset(local.secrets)
  secret_id = google_secret_manager_secret.secret[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  # todo replace with our specific service account with specific IAM
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}


resource "google_storage_bucket_access_control" "public_rule" {
  bucket = google_storage_bucket.output_bucket.name
  role   = "READER"
  entity = "allUsers"
}

resource "google_storage_bucket" "output_bucket" {
  name     = "output-${data.google_project.project.name}"
  location = "US"
}


resource "google_cloud_run_service" "freespeech_telegram" {
  name     = "freespeech-telegram"
  location = local.region

  template {
    spec {
      timeout_seconds = 1800
      containers {
        # todo change to correct image
        image = "us-docker.pkg.dev/cloudrun/container/hello"
        env {
          name = "TELEGRAM_BOT_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.secret["TELEGRAM_BOT_TOKEN"].secret_id
              key  = "1"
            }
          }
        }
        # todo enable args here
        #        args  = ["start-telegram"]
        env {
          name  = "FREESPEECH_CHAT_SERVICE_URL"
          value = google_cloud_run_service.freespeech_chat.status.0.url
        }
        # todo add link to webhook, but we have circular dep in async rollout
        #        env {
        #          name  = "https://CLOUD_RUN_ENDPOINT/tg_webhook"
        #          value = LINK TO OWN URL - CIRCULAR DEPENDENCY
        #        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service" "freespeech_chat" {
  name     = "freespeech-chat"
  location = local.region

  template {
    spec {
      containers {
        image = "us-docker.pkg.dev/cloudrun/container/hello"
        #        args  = ["start", "chat"]
        env {
          name  = "FREESPEECH_DUB_SERVICE_URL"
          value = google_cloud_run_service.freespeech_dub.status.0.url
        }
        env {
          name  = "FREESPEECH_CRUD_SERVICE_URL"
          value = google_cloud_run_service.freespeech_crud.status.0.url
        }
        env {
          name  = "FREESPEECH_STORAGE_BUCKET"
          value = google_storage_bucket.output_bucket.name
        }
      }
      timeout_seconds = 1800
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service" "freespeech_crud" {
  name     = "freespeech-crud"
  location = local.region

  template {
    spec {
      timeout_seconds = 1800
      containers {
        # todo change to correct image
        image = "us-docker.pkg.dev/cloudrun/container/hello"
        # todo enable args here
        #        args  = ["start crud"]
        env {
          name  = "FREESPEECH_STORAGE_BUCKET"
          value = google_storage_bucket.output_bucket.name
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service" "freespeech_dub" {
  name     = "freespeech-dub"
  location = local.region

  template {
    spec {
      timeout_seconds = 1800
      containers {
        # todo change to correct image
        image = "us-docker.pkg.dev/cloudrun/container/hello"
        # todo enable args here
        #        args  = ["start dub"]
        env {
          name  = "FREESPEECH_STORAGE_BUCKET"
          value = google_storage_bucket.output_bucket.name
        }
        env {
          name  = "AZURE_REGION"
          value = local.azure_region
        }
        env {
          name = "NOTION_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.secret["NOTION_TOKEN"].secret_id
              key  = "1"
            }
          }
        }
        env {
          name = "AZURE_SUBSCRIPTION_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.secret["AZURE_SUBSCRIPTION_KEY"].secret_id
              key  = "1"
            }
          }
        }
        # todo secret mount root/id/oauth_client_secret what is it?
        # todo secret youtube_credentials - what is it and how to get it?
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}


data "google_iam_policy" "noauth" {
  binding {
    role    = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

locals {
  public_services = {
    "telegram" = google_cloud_run_service.freespeech_telegram
    "chat"     = google_cloud_run_service.freespeech_chat
    "dub"      = google_cloud_run_service.freespeech_dub
    "crud"     = google_cloud_run_service.freespeech_crud
  }
}


resource "google_cloud_run_service_iam_policy" "noauth" {
  for_each = tomap(local.public_services)

  location = each.value.location
  project  = each.value.project
  service  = each.value.name

  policy_data = data.google_iam_policy.noauth.policy_data
}

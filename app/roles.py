from __future__ import annotations

import re
from urllib.parse import quote

TARGET_ROLES = [
    {
        "id": "cloud-devops",
        "label": "Cloud DevOps",
        "title_terms": (
            "devops",
            "dev ops",
            "sre",
            "site reliability",
            "cloud engineer",
            "cloud devops",
            "cloud infrastructure",
            "cloud ops",
            "cloud operations",
            "infrastructure devops",
            "kubernetes admin",
            "k8s admin",
        ),
        "linkedin": "Cloud DevOps OR DevOps Engineer OR SRE",
    },
    {
        "id": "aws",
        "label": "AWS",
        "title_terms": ("aws", "amazon web services"),
        "linkedin": "AWS Administrator OR AWS DevOps OR AWS Engineer",
    },
    {
        "id": "azure",
        "label": "Azure",
        "title_terms": ("azure",),
        "linkedin": "Azure Administrator OR Azure DevOps OR Azure Engineer",
    },
    {
        "id": "gcp",
        "label": "GCP",
        "title_terms": ("gcp", "google cloud"),
        "linkedin": "GCP Administrator OR Google Cloud Engineer OR GCP DevOps",
    },
    {
        "id": "openstack",
        "label": "OpenStack",
        "title_terms": ("openstack",),
        "linkedin": "OpenStack Administrator OR OpenStack Engineer",
    },
    {
        "id": "vmware",
        "label": "VMware",
        "title_terms": ("vmware", "v-sphere", "vsphere", "vcenter", "esxi"),
        "linkedin": "VMware Administrator OR VMware Engineer OR vSphere",
    },
    {
        "id": "linux-admin",
        "label": "Linux Admin",
        "title_terms": (
            "linux admin",
            "linux administrator",
            "linux system",
            "linux systems",
            "linux engineer",
            "rhel admin",
            "red hat admin",
            "unix admin",
            "unix administrator",
        ),
        "linkedin": "Linux Administrator OR Linux System Administrator OR Linux Engineer",
    },
    {
        "id": "windows-admin",
        "label": "Windows Admin",
        "title_terms": (
            "windows admin",
            "windows administrator",
            "windows system",
            "windows systems",
            "windows engineer",
            "windows server",
            "active directory",
            "microsoft admin",
        ),
        "linkedin": "Windows Administrator OR Windows System Administrator OR Active Directory",
    },
    {
        "id": "openshift",
        "label": "OpenShift Admin",
        "title_terms": ("openshift", "ocp admin", "okd"),
        "linkedin": "OpenShift Administrator OR OpenShift Engineer",
    },
    {
        "id": "app-support",
        "label": "Application Support",
        "title_terms": (
            "application support",
            "app support",
            "production support",
            "l1 support",
            "l2 support",
            "l3 support",
            "application operations",
            "ops support",
        ),
        "linkedin": "Application Support Engineer OR Production Support",
    },
]

GENERIC_ADMIN_TITLES = (
    "system administrator",
    "systems administrator",
    "sysadmin",
    "sys admin",
    "systems engineer",
    "system engineer",
    "infrastructure engineer",
    "infrastructure administrator",
    "it administrator",
    "it engineer",
    "cloud admin",
    "cloud administrator",
    "operations engineer",
    "platform administrator",
)

ROLE_SIGNALS = {
    "Cloud DevOps": ("devops", "kubernetes", "ci/cd", "terraform", "ansible", "sre"),
    "AWS": ("aws", "amazon web services", "ec2", "eks"),
    "Azure": ("azure", "aks"),
    "GCP": ("gcp", "google cloud", "gke"),
    "OpenStack": ("openstack",),
    "VMware": ("vmware", "vsphere", "vcenter", "esxi"),
    "Linux Admin": ("linux", "rhel", "red hat", "ubuntu", "unix"),
    "Windows Admin": ("windows server", "active directory", "powershell", "windows admin"),
    "OpenShift Admin": ("openshift", "ocp"),
}


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def classify_roles(title: str, description: str = "") -> list[str]:
    title_l = _clean(title)
    labels: list[str] = []
    for role in TARGET_ROLES:
        if any(term in title_l for term in role["title_terms"]):
            labels.append(role["label"])
    if labels:
        return labels

    if any(term in title_l for term in GENERIC_ADMIN_TITLES):
        blob = f"{title_l} {_clean(description)}"
        for label, signals in ROLE_SIGNALS.items():
            if any(term in blob for term in signals):
                labels.append(label)
    return labels


def is_target_role(title: str, description: str = "") -> bool:
    return bool(classify_roles(title, description))


def role_catalog() -> list[dict]:
    return [
        {
            "id": role["id"],
            "label": role["label"],
            "linkedin_url": (
                "https://www.linkedin.com/jobs/search/?f_TPR=r604800&keywords="
                + quote(role["linkedin"])
            ),
        }
        for role in TARGET_ROLES
    ]


DEFAULT_HEADLINE = "Cloud / DevOps and systems administrator (AWS, Azure, GCP, OpenShift, Linux, Windows, VMware)"
DEFAULT_SKILLS = (
    "Linux, Windows Server, AWS, Azure, GCP, OpenStack, VMware, OpenShift, "
    "Kubernetes, DevOps, Terraform, Ansible, CI/CD"
)
DEFAULT_PITCH = (
    "I work as a Cloud / DevOps and systems administrator across AWS, Azure, GCP, "
    "OpenStack, VMware, Linux, Windows, and OpenShift. I am comfortable with day-to-day "
    "admin work, cloud operations, and keeping production platforms reliable."
)
DEFAULT_WATCH_KEYWORDS = (
    "devops, aws, azure, gcp, openstack, vmware, linux administrator, "
    "windows administrator, openshift"
)

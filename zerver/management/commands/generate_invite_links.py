from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.email_validation import email_allowed_for_realm
from zerver.lib.management import ZulipBaseCommand
from zerver.models import DomainNotAllowedForRealmError, PreregistrationUser


class Command(ZulipBaseCommand):
    help = "Generate activation links for users and print them to stdout."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Override that the domain is restricted to external users.",
        )
        parser.add_argument(
            "--invite-expires-in-days",
            default=settings.INVITATION_LINK_VALIDITY_DAYS,
            type=int,
            help="Number of days before link expires.",
        )
        parser.add_argument(
            "emails",
            metavar="<email>",
            nargs="*",
            help="email of users to generate an activation link for",
        )
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: Any) -> None:
        duplicates = False
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        if not options["emails"]:
            self.print_help("./manage.py", "generate_invite_links")
            raise CommandError

        for email in options["emails"]:
            try:
                self.get_user(email, realm)
                print(email + ": There is already a user registered with that address.")
                duplicates = True
                continue
            except CommandError:
                pass

        if duplicates:
            return

        for email in options["emails"]:
            try:
                email_allowed_for_realm(email, realm)
            except DomainNotAllowedForRealmError:
                if not options["force"]:
                    raise CommandError(
                        "You've asked to add an external user '{}' to a "
                        "closed realm '{}'.\nAre you sure? To do this, "
                        "pass --force.".format(email, realm.string_id)
                    )

            prereg_user = PreregistrationUser(email=email, realm=realm)
            prereg_user.save()
            print(
                email
                + ": "
                + create_confirmation_link(
                    prereg_user,
                    Confirmation.INVITATION,
                    validity_in_days=options["invite_expires_in_days"],
                )
            )

from .create_credit_proposal_coril import lambda_handler as create_handler
from .delete_credit_proposal_coril import lambda_handler as delete_handler
from .delete_batch_credit_proposals_coril import lambda_handler as delete_batch_handler
from .download_credit_proposal_coril import lambda_handler as download_handler
from .get_credit_proposals_coril import lambda_handler as get_handler

__all__ = ['create_handler', 'delete_handler', 'delete_batch_handler', 'download_handler', 'get_handler']
